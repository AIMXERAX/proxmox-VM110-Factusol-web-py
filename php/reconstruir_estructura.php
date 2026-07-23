<?php
/**
 * Reconstruir Estructura de Base de Datos
 * ========================================
 * 
 * Este script reconstruye la estructura de las tablas MySQL desde cero.
 * 
 * PROCESO:
 * 1. Verifica código de autorización
 * 2. Lee el archivo SQL de estructura (iniciar_tablas_XXXX.sql)
 * 3. Ejecuta DROP TABLE y CREATE TABLE para cada tabla
 * 4. Crea los índices correspondientes
 * 
 * IMPORTANTE: Este script NO carga datos, solo recrea la estructura.
 * Después de ejecutar este script, debe ejecutarse aim_incremental_force_full.bat
 */

// Configuraciones para evitar timeouts
ini_set('max_execution_time', 600); // 10 minutos máximo
ini_set('memory_limit', '512M');
ob_implicit_flush(true);

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

// Archivo SQL de estructura (será detectado automáticamente)
$log_file = 'reconstruccion_estructura.log';

function escribir_log($mensaje) {
    global $log_file;
    $timestamp = date('Y-m-d H:i:s');
    $log_entry = "[$timestamp] $mensaje" . PHP_EOL;
    file_put_contents($log_file, $log_entry, FILE_APPEND | LOCK_EX);
}

function verificar_codigo($code) {
    global $palabra_clave_esperada;
    
    if (empty($code)) {
        return false;
    }
    
    return password_verify($palabra_clave_esperada, $code);
}

function encontrar_archivo_estructura() {
    // Buscar archivo iniciar_tablas_*.sql
    $archivos = glob('iniciar_tablas_*.sql');
    
    if (empty($archivos)) {
        throw new Exception("No se encontró archivo de estructura (iniciar_tablas_*.sql)");
    }
    
    // Si hay múltiples, usar el más reciente
    usort($archivos, function($a, $b) {
        return filemtime($b) - filemtime($a);
    });
    
    return $archivos[0];
}

function reconstruir_estructura() {
    global $servername, $username, $password, $dbname;
    
    try {
        escribir_log("=== INICIO DE RECONSTRUCCIÓN DE ESTRUCTURA ===");
        
        // Encontrar archivo SQL de estructura
        $sql_file = encontrar_archivo_estructura();
        escribir_log("Archivo de estructura encontrado: $sql_file");
        echo "Archivo de estructura: $sql_file\n";
        flush();
        
        $tamano_mb = round(filesize($sql_file) / 1024 / 1024, 2);
        escribir_log("Tamaño del archivo: {$tamano_mb} MB");
        
        // Conectar a MySQL
        $conn = new mysqli($servername, $username, $password, $dbname);
        
        if ($conn->connect_error) {
            throw new Exception("Error de conexión: " . $conn->connect_error);
        }
        
        escribir_log("Conexión a base de datos establecida");
        echo "Conexión establecida.\n";
        flush();
        
        // Configurar charset y modos SQL
        $conn->set_charset("utf8mb4");
        $conn->query("SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO'");
        $conn->query("SET NAMES utf8mb4");
        $conn->query("SET time_zone = '+00:00'");
        $conn->query("SET foreign_key_checks = 0");
        
        escribir_log("Configuraciones SQL aplicadas");
        
        // Leer archivo SQL completo
        echo "Leyendo archivo SQL...\n";
        flush();
        
        $sql_completo = file_get_contents($sql_file);
        if ($sql_completo === false) {
            throw new Exception("No se pudo leer el archivo SQL");
        }
        
        escribir_log("Archivo SQL leído correctamente");
        
        // Dividir en sentencias individuales
        echo "Procesando sentencias SQL...\n";
        flush();
        
        $tiempo_inicio = microtime(true);
        $ejecutadas = 0;
        $errores = 0;
        $tablas_eliminadas = 0;
        $tablas_creadas = 0;
        $indices_creados = 0;
        
        // Iniciar transacción
        $conn->autocommit(FALSE);
        $conn->begin_transaction();
        
        // Procesar línea por línea para mejor control
        $lineas = explode("\n", $sql_completo);
        $sentencia_actual = '';
        
        foreach ($lineas as $num_linea => $linea) {
            $linea_trim = trim($linea);
            
            // Ignorar comentarios y líneas vacías
            if (empty($linea_trim) || 
                strpos($linea_trim, '--') === 0 || 
                strpos($linea_trim, '/*') === 0 ||
                strpos($linea_trim, '/*!') === 0) {
                continue;
            }
            
            // Acumular línea
            $sentencia_actual .= $linea . " ";
            
            // Si termina con punto y coma, ejecutar
            if (substr($linea_trim, -1) === ';') {
                $sentencia = trim($sentencia_actual);
                
                // Determinar tipo de sentencia
                $primera_palabra = strtoupper(substr($sentencia, 0, 10));
                
                if (strpos($primera_palabra, 'DROP') === 0 ||
                    strpos($primera_palabra, 'CREATE') === 0 ||
                    strpos($primera_palabra, 'SET') === 0 ||
                    strpos($primera_palabra, 'START') === 0 ||
                    strpos($primera_palabra, 'COMMIT') === 0) {
                    
                    $ejecutadas++;
                    
                    // Ejecutar sentencia
                    $resultado = $conn->query($sentencia);
                    
                    if ($resultado === false) {
                        $errores++;
                        escribir_log("ERROR en sentencia #$ejecutadas: " . $conn->error);
                        escribir_log("Sentencia: " . substr($sentencia, 0, 200));
                        
                        echo "⚠️  Error en sentencia $ejecutadas: " . $conn->error . "\n";
                        flush();
                        
                        // Si hay muchos errores, abortar
                        if ($errores >= 20) {
                            throw new Exception("Demasiados errores ($errores), abortando");
                        }
                    } else {
                        // Contar tipos de operaciones
                        if (strpos($primera_palabra, 'DROP') === 0) {
                            $tablas_eliminadas++;
                            
                            // Extraer nombre de tabla para mostrar progreso
                            if (preg_match('/DROP TABLE IF EXISTS [`\']?([^`\'\s]+)[`\']?/', $sentencia, $matches)) {
                                echo "🗑️  DROP: {$matches[1]}\n";
                                flush();
                            }
                        } elseif (strpos($primera_palabra, 'CREATE TAB') !== false) {
                            $tablas_creadas++;
                            
                            // Extraer nombre de tabla
                            if (preg_match('/CREATE TABLE [`\']?([^`\'\s]+)[`\']?/', $sentencia, $matches)) {
                                echo "✅ CREATE: {$matches[1]}\n";
                                flush();
                            }
                        } elseif (strpos($primera_palabra, 'CREATE IND') !== false) {
                            $indices_creados++;
                        }
                    }
                    
                    // Commit parcial cada 50 operaciones
                    if ($ejecutadas % 50 == 0) {
                        $conn->commit();
                        $conn->begin_transaction();
                        echo "Checkpoint: $ejecutadas sentencias procesadas\n";
                        flush();
                    }
                }
                
                // Resetear buffer
                $sentencia_actual = '';
            }
        }
        
        // Commit final
        echo "Finalizando transacción...\n";
        flush();
        
        $conn->commit();
        escribir_log("Commit final ejecutado");
        
        $tiempo_fin = microtime(true);
        $tiempo_total = round($tiempo_fin - $tiempo_inicio, 2);
        
        // Estadísticas finales
        echo "\n" . str_repeat("=", 70) . "\n";
        echo "RECONSTRUCCIÓN DE ESTRUCTURA COMPLETADA\n";
        echo str_repeat("=", 70) . "\n";
        echo "Sentencias ejecutadas: " . number_format($ejecutadas) . "\n";
        echo "Tablas eliminadas (DROP): $tablas_eliminadas\n";
        echo "Tablas creadas (CREATE): $tablas_creadas\n";
        echo "Índices creados: $indices_creados\n";
        echo "Errores encontrados: $errores\n";
        echo "Tiempo total: {$tiempo_total}s\n";
        echo str_repeat("=", 70) . "\n";
        
        escribir_log("=== RECONSTRUCCIÓN COMPLETADA ===");
        escribir_log("Sentencias: $ejecutadas | Tablas DROP: $tablas_eliminadas | Tablas CREATE: $tablas_creadas | Índices: $indices_creados | Errores: $errores");
        escribir_log("Tiempo: {$tiempo_total}s");
        
        if ($errores > 0) {
            echo "\n⚠️  ADVERTENCIA: Se encontraron $errores errores. Revise el log.\n";
        } else {
            echo "\n✅ Estructura reconstruida exitosamente sin errores.\n";
        }
        
        echo "\n⚠️  IMPORTANTE: Ahora debe ejecutar la carga de datos (aim_incremental_force_full.bat)\n";
        
        $conn->close();
        
        return "Reconstrucción completada: $tablas_creadas tablas creadas, $errores errores";
        
    } catch (Exception $e) {
        if (isset($conn)) {
            escribir_log("Rollback por error: " . $e->getMessage());
            $conn->rollback();
            $conn->close();
        }
        
        $mensaje_error = "Error crítico: " . $e->getMessage();
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

// Ejecutar reconstrucción
try {
    $resultado = reconstruir_estructura();
    echo "\n$resultado\n";
} catch (Exception $e) {
    http_response_code(500);
    echo "Error interno del servidor: " . $e->getMessage();
    escribir_log("Error crítico: " . $e->getMessage());
}

?>
