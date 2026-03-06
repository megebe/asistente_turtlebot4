#!/usr/bin/env python3
"""
Script de diagnóstico: detecta el micrófono disponible, graba 4 s y transcribe con whisper-cli.
Ejecutar directamente: python3 test_whisper.py
"""

import subprocess
import sys
import os
import re

RUTA_WHISPER = '/home/m/voice_controlled_turtlebot/whisper.cpp'
BINARIO      = f'{RUTA_WHISPER}/build/bin/whisper-cli'
MODELO       = f'{RUTA_WHISPER}/models/ggml-base.bin'
WAV_TEMP     = '/tmp/test_whisper.wav'
DURACION_SEG = 4


# ---------------------------------------------------------------------------
# 1. Verificar que el binario y el modelo existen
# ---------------------------------------------------------------------------
def verificar_binarios():
    ok = True
    for ruta in [BINARIO, MODELO]:
        if os.path.exists(ruta):
            print(f'  [OK] {ruta}')
        else:
            print(f'  [ERROR] No encontrado: {ruta}')
            ok = False
    return ok


# ---------------------------------------------------------------------------
# 2. Detectar dispositivo de micrófono
# ---------------------------------------------------------------------------
def detectar_dispositivo():
    """
    Devuelve el nombre ALSA del primer dispositivo de captura disponible.
    Prueba en orden: 'default', 'plughw:0,0', 'plughw:0,1'.
    """
    try:
        salida = subprocess.run(['arecord', '-l'], capture_output=True, text=True).stdout
        print('\nDispositivos de captura detectados:')
        print(salida.strip())
    except FileNotFoundError:
        print('[ERROR] arecord no encontrado. Instala alsa-utils.')
        return None

    candidatos = ['default']

    # Extrae plughw:card,device de la salida de arecord -l
    for match in re.finditer(r'card (\d+).*?device (\d+)', salida):
        card, dev = match.group(1), match.group(2)
        candidatos.append(f'plughw:{card},{dev}')

    # Prueba cada candidato grabando 1 segundo silencioso
    for disp in candidatos:
        resultado = subprocess.run([
            'arecord', '-D', disp, '-f', 'S16_LE', '-r', '16000',
            '-c', '1', '-t', 'wav', '-d', '1', '/tmp/_probe.wav'
        ], capture_output=True)
        if resultado.returncode == 0:
            print(f'\n  [OK] Dispositivo seleccionado: {disp}')
            return disp
        else:
            print(f'  [FALLO] {disp}: {resultado.stderr.decode().strip()}')

    return None


# ---------------------------------------------------------------------------
# 3. Grabar audio
# ---------------------------------------------------------------------------
def grabar(dispositivo):
    print(f'\nGrabando {DURACION_SEG} s desde "{dispositivo}"... (habla ahora)')
    r = subprocess.run([
        'arecord', '-D', dispositivo,
        '-f', 'S16_LE', '-r', '16000', '-c', '1',
        '-t', 'wav', '-d', str(DURACION_SEG),
        WAV_TEMP
    ], capture_output=True)
    if r.returncode != 0:
        print(f'[ERROR] arecord: {r.stderr.decode().strip()}')
        return False
    size = os.path.getsize(WAV_TEMP)
    print(f'  [OK] WAV guardado en {WAV_TEMP} ({size} bytes)')
    return True


# ---------------------------------------------------------------------------
# 4. Transcribir con whisper-cli
# ---------------------------------------------------------------------------
def transcribir():
    print('\nTranscribiendo con whisper-cli...')
    r = subprocess.run([
        BINARIO,
        '-m', MODELO,
        '-f', WAV_TEMP,
        '-l', 'es',      # idioma español; cambia a 'auto' si prefieres detección automática
        '--no-gpu',
    ], capture_output=True, text=True)

    print(f'  Código de salida: {r.returncode}')

    if r.stderr.strip():
        print('  [stderr]')
        for linea in r.stderr.strip().splitlines()[-10:]:
            print(f'    {linea}')

    print('\n  [stdout completo]')
    if r.stdout.strip():
        for linea in r.stdout.strip().splitlines():
            print(f'    {linea}')
    else:
        print('    (vacío)')

    # Extraer fragmentos con formato [HH:MM:SS --> HH:MM:SS] texto
    fragmentos = []
    for linea in r.stdout.splitlines():
        if '-->' in linea and ']' in linea:
            texto = linea.split(']', 1)[-1].strip()
            if texto:
                fragmentos.append(texto)

    if fragmentos:
        transcripcion = ' '.join(fragmentos)
        print(f'\n  Transcripcion final: "{transcripcion}"')
    else:
        print('\n  [WARN] No se extrajeron fragmentos con formato timestamp.')
        print('  Verifica el stdout completo de arriba.')

    return r.returncode == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    print('=== Test Whisper ===\n')

    print('1. Verificando binarios...')
    if not verificar_binarios():
        sys.exit(1)

    print('\n2. Detectando micrófono...')
    dispositivo = detectar_dispositivo()
    if dispositivo is None:
        print('[ERROR] No se encontró ningún dispositivo de captura funcional.')
        sys.exit(1)

    print('\n3. Grabando...')
    if not grabar(dispositivo):
        sys.exit(1)

    print('\n4. Transcribiendo...')
    ok = transcribir()

    print('\n=== Fin del test ===')
    sys.exit(0 if ok else 1)
