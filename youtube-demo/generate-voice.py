"""
HAMSVIC Office — Voice narration generator.
Supports: OpenAI TTS, ElevenLabs, Google Cloud TTS, local espeak-ng fallback.
Outputs: voice.mp3
"""
import os
import sys

NARRATION_FILE = os.path.join(os.path.dirname(__file__), 'narration.txt')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), 'voice.mp3')


def read_narration():
    with open(NARRATION_FILE, 'r') as f:
        lines = f.readlines()
    text_lines = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('[') or line.startswith('='):
            continue
        if line.startswith('HAMSVIC Office') and 'Narration' in line:
            continue
        text_lines.append(line)
    return ' '.join(text_lines)


def try_openai_tts(text):
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        return False
    print('[TTS] Using OpenAI Text-to-Speech...')
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.audio.speech.create(
            model='tts-1-hd',
            voice='onyx',
            input=text,
            speed=0.95,
        )
        response.stream_to_file(OUTPUT_FILE)
        print(f'[TTS] Voice saved: {OUTPUT_FILE}')
        return True
    except Exception as e:
        print(f'[TTS] OpenAI TTS failed: {e}')
        return False


def try_elevenlabs_tts(text):
    api_key = os.environ.get('ELEVEN_LABS_API_KEY', '')
    if not api_key:
        return False
    print('[TTS] Using ElevenLabs...')
    try:
        import requests
        url = 'https://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB'
        headers = {
            'xi-api-key': api_key,
            'Content-Type': 'application/json',
        }
        data = {
            'text': text,
            'model_id': 'eleven_multilingual_v2',
            'voice_settings': {
                'stability': 0.5,
                'similarity_boost': 0.75,
            },
        }
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        with open(OUTPUT_FILE, 'wb') as f:
            f.write(response.content)
        print(f'[TTS] Voice saved: {OUTPUT_FILE}')
        return True
    except Exception as e:
        print(f'[TTS] ElevenLabs failed: {e}')
        return False


def try_google_tts(text):
    creds = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '')
    if not creds:
        return False
    print('[TTS] Using Google Cloud TTS...')
    try:
        from google.cloud import texttospeech
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code='en-IN',
            name='en-IN-Wavenet-C',
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=0.95,
        )
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        with open(OUTPUT_FILE, 'wb') as f:
            f.write(response.audio_content)
        print(f'[TTS] Voice saved: {OUTPUT_FILE}')
        return True
    except Exception as e:
        print(f'[TTS] Google TTS failed: {e}')
        return False


def try_local_espeak(text):
    import subprocess
    try:
        subprocess.run(
            ['espeak-ng', '-v', 'en-us', '-w', OUTPUT_FILE, text[:4000]],
            check=True, capture_output=True,
        )
        print(f'[TTS] Voice saved (espeak-ng): {OUTPUT_FILE}')
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def main():
    text = read_narration()
    print(f'[TTS] Narration: {len(text)} characters')

    for fn in [try_openai_tts, try_elevenlabs_tts, try_google_tts, try_local_espeak]:
        if fn(text):
            return

    print('\n[TTS] No TTS service available.')
    print('To generate voice, set one of these environment variables:')
    print('  export OPENAI_API_KEY=sk-...')
    print('  export ELEVEN_LABS_API_KEY=...')
    print('  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json')
    print('Then re-run: python3 generate-voice.py')
    sys.exit(1)


if __name__ == '__main__':
    main()
