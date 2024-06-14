from fastapi import FastAPI, HTTPException
from pytube import YouTube
from fastapi.responses import FileResponse
import os
from starlette.background import BackgroundTask
import subprocess
import threading
from datetime import datetime, timedelta

app = FastAPI()

DOWNLOAD_FOLDER = "temp_downloads"
file_management = {}

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

def delete_file(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)
    # Hapus entri dari file_management setelah file dihapus
    if file_path in file_management:
        del file_management[file_path]

def manage_file_deletion(file_path, delay=300):
    if file_path in file_management:
        # Jika file sudah ada, perbarui waktu penghapusan dan tambah counter
        file_management[file_path]['counter'] += 1
        file_management[file_path]['timer'].cancel()
    else:
        # Jika file baru, buat entri baru
        file_management[file_path] = {'counter': 1}
    
    # Set timer baru dengan delay yang disesuaikan berdasarkan jumlah permintaan
    new_delay = delay + (file_management[file_path]['counter'] * 60)  # Tambah 1 menit per permintaan
    timer = threading.Timer(new_delay, delete_file, [file_path])
    timer.start()
    file_management[file_path]['timer'] = timer

@app.get("/")
async def read_root():
    return {"message": "Welcome to the YouTube video downloader API!"}
    
@app.get("/resolutions/")
async def list_dash_resolutions(url: str):
    try:
        yt = YouTube(url)
        dash_streams = yt.streams.filter(adaptive=True).order_by('resolution').desc()
        video_resolutions = [stream.resolution for stream in dash_streams if stream.includes_video_track]
        return {"dash_resolutions": video_resolutions}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/download/")
async def download_video(url: str, resolution: str):
    try:
        yt = YouTube(url)
        if resolution == "1080p":
            video = yt.streams.filter(res=resolution, mime_type="video/mp4").first()
            audio = yt.streams.filter(only_audio=True).first()
            if video is None or audio is None:
                return {"error": "Resolusi atau audio tidak tersedia."}
            video_file_name = f"video_{yt.title}.mp4".replace(" ", "_").replace("/", "_")
            audio_file_name = f"audio_{yt.title}.mp4".replace(" ", "_").replace("/", "_")
            video.download(filename=video_file_name)
            audio.download(filename=audio_file_name)
            filename = f"{yt.title} {resolution}.mp4".replace(" ", "_").replace("/", "_")
            output_file_name = os.path.join(DOWNLOAD_FOLDER, filename)
            ffmpeg_command = [
                'ffmpeg',
                '-i', video_file_name,
                '-i', audio_file_name,
                '-c', 'copy',
                output_file_name
            ]
            subprocess.run(ffmpeg_command, check=True)
            # Hapus file sementara setelah penggabungan
            os.remove(video_file_name)
            os.remove(audio_file_name)
            file_path = os.path.join(DOWNLOAD_FOLDER, output_file_name)
        else:
            video = yt.streams.filter(res=resolution, file_extension='mp4').first()
            if video is None:
                return {"error": "Resolusi tidak tersedia."}
            filename = f"{yt.title} {resolution}.mp4".replace(" ", "_").replace("/", "_")
            file_path = os.path.join(DOWNLOAD_FOLDER, filename)
            video.download(filename=file_path)
        
        return {"success": True, "filename": filename}
    except subprocess.CalledProcessError as e:
        # Jika terjadi kesalahan saat menjalankan FFmpeg, hapus file yang mungkin telah diunduh
        if os.path.exists(video_file_name):
            os.remove(video_file_name)
        if os.path.exists(audio_file_name):
            os.remove(audio_file_name)
        return {"error": f"Kesalahan saat menjalankan FFmpeg: {e}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/download-file/")
async def download_file(url: str, resolution: str):
    yt = YouTube(url)
    filename = f"{yt.title}_{resolution}.mp4".replace(" ", "_").replace("/", "_")
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    
    # Logika untuk mengunduh file ke file_path di sini
    
    if os.path.exists(file_path):
        # Atur atau perbarui pengelolaan file dan penghapusan
        manage_file_deletion(file_path)
        
        return FileResponse(path=file_path, filename=filename, media_type='application/octet-stream')
    else:
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")

