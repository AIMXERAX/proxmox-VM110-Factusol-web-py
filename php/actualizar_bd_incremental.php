<?php
/**
 * Actualizar BD Factusol - Versión Incremental
 * Este script procesa actualizaciones incrementales de la base de datos
 * Solo ejecuta los cambios necesarios en lugar de recrear todas las tablas
 */

// Configuraciones para evitar timeouts
ini_set('max_execution_time', 600); // 10 minutos máximo
ini_set('memory_limit', '512M'); // Aumentar memoria disponible
ob_implicit_flush(true); // Enviar output inmediatamente al cliente

// Cargar configuración desde .env local
function load_env($path) {
    if (!file_exists($path)) return;
    foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        $line = trim($line);
        if ($line === '' || $line[0] === '#' || strpos($line, '=') === false) continue;
        [$key, $value] = explode('=', $line, 2);
        $_ENV[trim($key)] = trim($value);
    }
}
load_env(__DIR__ . '/.env');

$servername = $_ENV['DB_HOST'] ?? '';
$username   = $_ENV['DB_USER'] ?? '';
$password   = $_ENV['DB_PASSWORD'] ?? '';
$dbname     = $_ENV['DB_NAME'] ?? '';

// Configuración de seguridad
$palabra_clave_esperada = $_ENV['PALABRA_CLAVE'] ?? '';

// Archivo SQL de actualización incremental
$sql_file = 'tablas_aim_incremental.sql';

// Log de operaciones
$log_file = 'actualizacion_incremental.log';

function escribir_log($mensaje) {
    global $log_file;
    $timestamp = date('Y-m-d H:i:s');
    $log_entry = "[$timestamp] $mensaje" . PHP_EOL;
    file_put_contents($log_file, $log_entry, FILE_APPEND | LOCK_EX);
}

function verificar_codigo($code) {
    global $palabra_clave_esperada;
    
    // Verificar que el código no esté vacío
    if (empty($code)) {
        return false;
    }
    
    // Verificar el hash bcrypt
    return password_verify($palabra_clave_esperada, $code);
}

function ejecutar_actualizacion_incremental() {
    global $servername, $username, $password, $dbname, $sql_file;
    
    try {
        escribir_log("=== INICIO DE ACTUALIZACIÓN SIMPLIFICADA ===");
        
        // Verificar que existe el archivo SQL
        if (!file_exists($sql_file)) {
            throw new Exception("Archivo SQL no encontrado: $sql_file");
        }
        
        escribir_log("Archivo SQL encontrado: $sql_file");
        
        $tamano_mb = round(filesize($sql_file) / 1024 / 1024, 2);
        escribir_log("Tamaño del archivo: {$tamano_mb} MB");
        
        // Crear conexión a MySQL
        $conn = new mysqli($servername, $username, $password, $dbname);
        
        if ($conn->connect_error) {
            throw new Exception("Error de conexión: " . $conn->connect_error);
        }
        
        escribir_log("Conexión a base de datos establecida");
        
        // Configurar charset
        $conn->set_charset("utf8mb4");
        
        // Configuraciones SQL idénticas a phpMyAdmin
        $conn->query("SET SQL_MODE = ''");
        $conn->query("SET NAMES utf8mb4");
        $conn->query("SET time_zone = '+00:00'");
        $conn->query("SET foreign_key_checks = 0");
        $conn->query("SET sql_mode = 'NO_AUTO_VALUE_ON_ZERO'");
        
        // Configuraciones básicas de timeout
        $conn->query("SET SESSION wait_timeout = 300");
        $conn->query("SET SESSION interactive_timeout = 300");
        
        escribir_log("Configuraciones SQL aplicadas (modo phpMyAdmin)");
        
        // Verificar la base de datos en uso
        $db_actual = $conn->query("SELECT DATABASE()")->fetch_row()[0];
        escribir_log("Base de datos en uso: $db_actual");
        
        echo "Conexión establecida. Procesando SQL...\n";
        flush();
        
        // Procesar SQL línea por línea (sin cargar todo en memoria)
        escribir_log("Preparando procesamiento línea por línea...");
        
        // Abrir archivo para lectura
        $handle = fopen($sql_file, 'r');
        if (!$handle) {
            throw new Exception("No se pudo abrir el archivo SQL para lectura");
        }
        
        escribir_log("Archivo abierto, iniciando procesamiento directo...");
        
        echo "Procesando línea por línea...\n";
        flush();
        
        // Estimar total de sentencias (aproximadamente 1 sentencia por línea en promedio)
        $lineas_totales_estimadas = 300000; // Ajustar según archivo
        
        // Comenzar transacción
        $conn->autocommit(FALSE);
        $conn->begin_transaction();
        
        escribir_log("Transacción iniciada");
        
        $tiempo_inicio = microtime(true);
        $ejecutadas = 0;
        $errores = 0;
        $lineas_leidas = 0;
        $sentencia_actual = '';
        $ultimo_progreso_mostrado = -1;
        
        echo "Iniciando procesamiento...\n";
        flush();
        
        // Leer archivo línea por línea
        while (($linea = fgets($handle)) !== false) {
            $lineas_leidas++;
            
            // Mostrar progreso cada vez que se complete un 10%
            if ($ejecutadas > 0) {
                $progreso_actual = floor(($lineas_leidas / $lineas_totales_estimadas) * 10) * 10;
                if ($progreso_actual != $ultimo_progreso_mostrado && $progreso_actual % 10 == 0 && $progreso_actual > 0) {
                    echo "Procesando... {$progreso_actual}% (" . number_format($ejecutadas) . " sentencias)\n";
                    flush();
                    $ultimo_progreso_mostrado = $progreso_actual;
                }
            }
            
            // Ignorar líneas vacías o comentarios
            $linea_trim = trim($linea);
            if (empty($linea_trim) || strpos($linea_trim, '--') === 0 || strpos($linea_trim, '/*') === 0) {
                continue;
            }
            
            // Agregar línea a la sentencia actual
            $sentencia_actual .= $linea;
            
            // Si la línea termina con punto y coma, ejecutar la sentencia
            if (substr(rtrim($linea), -1) === ';') {
                $sentencia_completa = trim($sentencia_actual);
                
                // Verificar que sea INSERT/UPDATE/DELETE/TRUNCATE
                $primera_palabra = strtoupper(substr($sentencia_completa, 0, 8));
                
                if (strpos($primera_palabra, 'INSERT') === 0 || 
                    strpos($primera_palabra, 'UPDATE') === 0 || 
                    strpos($primera_palabra, 'DELETE') === 0 ||
                    strpos($primera_palabra, 'TRUNCATE') === 0 ||
                    strpos($primera_palabra, 'REPLACE') === 0) {
                    
                    $ejecutadas++;
                    
                    // Guardar la sentencia actual por si falla el script
                    $ultima_sentencia = $sentencia_completa;
                    $numero_sentencia_actual = $ejecutadas;
                    
                    // Ejecutar sentencia directamente
                    $resultado = $conn->query($sentencia_completa);
                    
                    if ($resultado === false) {
                        $errores++;
                        $error_msg = $conn->error;
                        $errno = $conn->errno;
                        $sqlstate = $conn->sqlstate;
                        
                        escribir_log("========== ERROR EN SENTENCIA #$ejecutadas ==========");
                        escribir_log("Línea aproximada: $lineas_leidas");
                        escribir_log("ERROR MySQL #$errno (SQLSTATE: $sqlstate): $error_msg");
                        escribir_log("Info de conexión:");
                        escribir_log("  - Host: " . $conn->host_info);
                        escribir_log("  - Charset: " . $conn->character_set_name());
                        escribir_log("  - Estado: " . ($conn->ping() ? "Activa" : "Inactiva"));
                        escribir_log("SENTENCIA SQL COMPLETA QUE CAUSÓ EL ERROR:");
                        escribir_log($sentencia_completa);
                        escribir_log("===================================================");
                        escribir_log("");  // Línea en blanco para separación
                        
                        // También mostrar en pantalla para debug inmediato
                        echo "\n*** ERROR #$errores en sentencia $ejecutadas ***\n";
                        echo "Error MySQL #$errno: $error_msg\n";
                        echo "Sentencia (primeros 200 chars): " . substr($sentencia_completa, 0, 200) . "...\n";
                        echo "Ver log para sentencia SQL completa\n\n";
                        flush();
                        
                        // Si es el primer error, registrar contexto adicional
                        if ($errores == 1) {
                            escribir_log("CONTEXTO: Este es el primer error encontrado");
                            escribir_log("Operaciones exitosas hasta ahora: " . ($ejecutadas - 1));
                        }
                        
                        // Si hay demasiados errores, abortar
                        if ($errores >= 50) {
                            escribir_log("ABORTANDO: Se alcanzó el límite de $errores errores");
                            throw new Exception("Demasiados errores SQL ($errores), abortando");
                        }
                    }
                    
                    // Commit parcial cada 1000 operaciones
                    if ($ejecutadas % 1000 == 0) {
                        try {
                            $conn->commit();
                            $conn->begin_transaction();
                            // Solo log cada 50000 para no saturar
                            if ($ejecutadas % 50000 == 0) {
                                escribir_log("Checkpoint: $ejecutadas sentencias procesadas correctamente");
                            }
                        } catch (Exception $commit_error) {
                            escribir_log("========== ERROR EN COMMIT PARCIAL ==========");
                            escribir_log("Sentencia #$ejecutadas");
                            escribir_log("Error: " . $commit_error->getMessage());
                            escribir_log("MySQL Error: " . $conn->error);
                            escribir_log("=============================================");
                            throw $commit_error;
                        }
                    }
                }
                
                // Resetear buffer de sentencia
                $sentencia_actual = '';
            }
        }
        
        // Cerrar archivo
        fclose($handle);
        escribir_log("=== PROCESAMIENTO COMPLETADO ===");
        escribir_log("Líneas leídas: " . number_format($lineas_leidas));
        escribir_log("Sentencias ejecutadas: " . number_format($ejecutadas));
        escribir_log("Errores encontrados: $errores");
        
        // Commit final
        echo "Finalizando transacción...\n";
        flush();
        
        try {
            $conn->commit();
            escribir_log("Commit final ejecutado correctamente");
        } catch (Exception $e) {
            escribir_log("ERROR EN COMMIT FINAL: " . $e->getMessage());
            throw $e;
        }
        
        $tiempo_fin = microtime(true);
        $tiempo_total = round($tiempo_fin - $tiempo_inicio, 2);
        $sentencias_por_segundo = round($ejecutadas / $tiempo_total, 2);
        
        // Construir mensaje final con estadísticas
        if ($errores > 0) {
            $mensaje_final = "⚠️  Actualización completada CON ERRORES";
            $estadisticas = "Procesadas: " . number_format($ejecutadas) . " | Errores: $errores | Tiempo: {$tiempo_total}s | Velocidad: {$sentencias_por_segundo} sent/s";
        } else {
            $mensaje_final = "✅ Actualización completada EXITOSAMENTE";
            $estadisticas = "Procesadas: " . number_format($ejecutadas) . " | Errores: 0 | Tiempo: {$tiempo_total}s | Velocidad: {$sentencias_por_segundo} sent/s";
        }
        
        escribir_log("=== FIN DE ACTUALIZACIÓN ===");
        escribir_log($mensaje_final);
        escribir_log($estadisticas);
        
        echo "\n" . $mensaje_final . "\n";
        echo $estadisticas . "\n";
        flush();
        
        $conn->close();
        
        return $mensaje_final;
        
    } catch (Exception $e) {
        // Registrar la última sentencia que se estaba procesando
        if (isset($ultima_sentencia)) {
            escribir_log("========== ÚLTIMA SENTENCIA ANTES DEL ERROR FATAL ==========");
            escribir_log("Número de sentencia: $numero_sentencia_actual");
            escribir_log("Total ejecutadas antes del error: $ejecutadas");
            escribir_log("SENTENCIA COMPLETA:");
            escribir_log($ultima_sentencia);
            escribir_log("===========================================================");
        }
        
        if (isset($conn)) {
            // No hacer rollback automático, puede haber sido un error menor
            escribir_log("Conexión cerrada sin rollback (revisar errores individuales)");
            $conn->close();
        }
        
        $mensaje_error = "Error en actualización: " . $e->getMessage();
        escribir_log($mensaje_error);
        escribir_log("=== FIN CON ERROR ===");
        
        return $mensaje_error;
    }
}

// Procesar la petición
header('Content-Type: text/plain; charset=utf-8');

// Verificar método HTTP
if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    http_response_code(405);
    echo "Método no permitido";
    escribir_log("Intento de acceso con método no permitido: " . $_SERVER['REQUEST_METHOD']);
    exit;
}

// Verificar código de autorización
$code = isset($_GET['code']) ? $_GET['code'] : '';

if (!verificar_codigo($code)) {
    http_response_code(401);
    echo "Código de autorización inválido";
    escribir_log("Intento de acceso no autorizado desde IP: " . ($_SERVER['REMOTE_ADDR'] ?? 'desconocida'));
    exit;
}

// Registrar acceso autorizado
escribir_log("Acceso autorizado desde IP: " . ($_SERVER['REMOTE_ADDR'] ?? 'desconocida'));

// Ejecutar actualización
try {
    $resultado = ejecutar_actualizacion_incremental();
    echo $resultado;
} catch (Exception $e) {
    http_response_code(500);
    echo "Error interno del servidor: " . $e->getMessage();
    escribir_log("Error crítico: " . $e->getMessage());
}

?>