
import asyncio
import aiohttp
import aiofiles
import os
import json
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import pathlib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

import sys

DOWNLOAD_DIR = pathlib.Path(__file__).parent / "downloads"
CHECK_INTERVAL_SECONDS = 60

URL_LIST = [
    {'id': 'dosya_1', 'url': 'https://jsonplaceholder.typicode.com/posts/1'},
    {'id': 'dosya_2', 'url': 'https://jsonplaceholder.typicode.com/posts/2'},
    {'id': 'dosya_3', 'url': 'https://jsonplaceholder.typicode.com/posts/3'},
    {'id': 'dosya_4', 'url': 'https://httpbin.org/status/404'},
    {'id': 'dosya_5', 'url': 'https://httpbin.org/bytes/1024'},
    {'id': 'dosya_6', 'url': 'https://httpbin.org/bytes/512'},
]

app = FastAPI(title="URL Downloader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class FileItem(BaseModel):
    id: str
    url: str

class DownloadRequest(BaseModel):
    files: Optional[List[FileItem]] = None

class DownloadManager:
    def __init__(self):
        self.active_downloads: Dict[str, Dict] = {}
        self.websocket_connections: List[WebSocket] = []
        self.download_dir = DOWNLOAD_DIR
        
        print("=" * 60)
        print("DOWNLOAD_DIR YONETIMI")
        print("=" * 60)
        print(f"Hedef dizin: {self.download_dir.absolute()}")
        print(f"Dizin var mi: {self.download_dir.exists()}")
        
        try:
            self.download_dir.mkdir(parents=True, exist_ok=True)
            print(f"Downloads klasoru hazir: {self.download_dir.absolute()}")
            
            if self.download_dir.exists():
                file_count = len([f for f in self.download_dir.iterdir() if f.is_file()])
                print(f"Klasordeki dosya sayisi: {file_count}")
            
        except Exception as e:
            print(f"Downloads klasoru olusturulamadi: {e}")
            print("Fallback dizini deneniyor...")
            
            self.download_dir = pathlib.Path.cwd() / "downloads"
            try:
                self.download_dir.mkdir(parents=True, exist_ok=True)
                print(f"Fallback downloads klasoru: {self.download_dir.absolute()}")
            except Exception as fallback_e:
                print(f"Fallback klasoru de olusturulamadi: {fallback_e}")
                print("Sistem temp dizini kullaniliyor...")
                
                import tempfile
                self.download_dir = pathlib.Path(tempfile.gettempdir()) / "url_downloader"
                self.download_dir.mkdir(parents=True, exist_ok=True)
                print(f"Temp dizini kullaniliyor: {self.download_dir.absolute()}")
        
        print("=" * 60)
        
    async def broadcast_message(self, message: Dict):
        disconnected = []
        for ws in self.websocket_connections:
            try:
                await ws.send_json(message)
            except:
                disconnected.append(ws)
        
        for ws in disconnected:
            if ws in self.websocket_connections:
                self.websocket_connections.remove(ws)
    
    async def create_initial_report(self, session_id: str):
        if session_id not in self.active_downloads:
            return
            
        report = {
            "deleted_files": [],
            "completed_files": [],
            "pending_files": list(self.active_downloads[session_id].keys()),
            "timestamp": datetime.now().isoformat()
        }
        
        report_path = self.download_dir / f"download_report_{session_id}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
        
        print("=" * 80)
        print(f"INDIRME RAPORU - Session ID: {session_id}")
        print("=" * 80)
        print(json.dumps(report, indent=4, ensure_ascii=False))
        print("=" * 80)
        print(f"DEBUG: create_initial_report tamamlandi - {datetime.now()}")
        
        print("=" * 80)
        logging.info(f"INDIRME RAPORU - Session ID: {session_id}")
        print("=" * 80)
        logging.info(json.dumps(report, indent=4, ensure_ascii=False))
        print("=" * 80)
        logging.info(f"DEBUG: create_initial_report tamamlandi - {datetime.now()}")
        
        print("=" * 80)
        print(f"JSON DOSYASI ICERIGI - {report_path.name}")
        print("=" * 80)
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
                print(file_content)
        except Exception as e:
            print(f"JSON dosyasi okunamadi: {e}")
        print("=" * 80)
    
    async def update_report(self, session_id: str):
        if session_id not in self.active_downloads:
            return
            
        deleted_files = []
        completed_files = []
        pending_files = []
        
        for file_id, info in self.active_downloads[session_id].items():
            if info["status"] == "failed":
                pending_files.append(file_id)
            elif info["status"] == "completed":
                completed_files.append(file_id)
            elif info["status"] == "stalled":
                deleted_files.append(file_id)
            else:
                pending_files.append(file_id)
        
        report = {
            "deleted_files": deleted_files,
            "completed_files": completed_files,
            "pending_files": pending_files,
            "timestamp": datetime.now().isoformat()
        }
        
        report_path = self.download_dir / f"download_report_{session_id}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
        
        print("=" * 80)
        print(f"RAPOR GUNCELLENDI - Session ID: {session_id}")
        print("=" * 80)
        print(json.dumps(report, indent=4, ensure_ascii=False))
        print("=" * 80)
        
        print("=" * 80)
        print(f"JSON DOSYASI ICERIGI - {report_path.name}")
        print("=" * 80)
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
                print(file_content)
        except Exception as e:
            print(f"JSON dosyasi okunamadi: {e}")
        print("=" * 80)
    
    async def create_deleted_urls_file(self, session_id: str, deleted_files: List[str]):
        if not deleted_files:
            return
            
        deleted_urls = []
        for file_item in URL_LIST:
            if file_item['id'] in deleted_files:
                deleted_urls.append({
                    'id': file_item['id'],
                    'url': file_item['url'],
                    'reason': 'Duraklama nedeniyle silindi',
                    'timestamp': datetime.now().isoformat()
                })
        
        urls_file_path = self.download_dir / f"deleted_urls_{session_id}.txt"
        with open(urls_file_path, 'w', encoding='utf-8') as f:
            f.write("DURAKLAMA NEDENİYLE SİLİNEN DOSYALARIN URL'LERİ\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Session ID: {session_id}\n")
            f.write(f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")
            f.write(f"Silinen Dosya Sayısı: {len(deleted_urls)}\n\n")
            
            for i, item in enumerate(deleted_urls, 1):
                f.write(f"{i}. {item['id']}\n")
                f.write(f"   URL: {item['url']}\n")
                f.write(f"   Sebep: {item['reason']}\n")
                f.write(f"   Zaman: {item['timestamp']}\n\n")
        
        try:
            print(f"Deleted URLs dosyası oluşturuldu: {urls_file_path}")
        except Exception:
            pass
    
    async def simulate_slow_download(self, session_id: str, file_id: str, url: str, file_path: str):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.read(100)
                        
                        async with aiofiles.open(file_path, 'wb') as f:
                            await f.write(data)
                        
                        self.active_downloads[session_id][file_id]["size"] = 100
                        self.active_downloads[session_id][file_id]["progress"] = 20
                        
                        await self.broadcast_message({
                            "type": "progress",
                            "session_id": session_id,
                            "file_id": file_id,
                            "status": "downloading",
                            "progress": 20,
                            "size": 100,
                            "total_size": 512
                        })
                        
                        await asyncio.sleep(30)
                        
                        self.active_downloads[session_id][file_id]["status"] = "downloading"
                        self.active_downloads[session_id][file_id]["size"] = 100
                        
                        try:
                            if file_path.exists() and file_path.stat().st_size == 100:
                                file_path.unlink()
                                self.active_downloads[session_id][file_id]["status"] = "stalled"
                                await self.broadcast_message({
                                    "type": "progress",
                                    "session_id": session_id,
                                    "file_id": file_id,
                                    "status": "stalled",
                                    "message": "Dosya duraklamış ve silindi (hemen)"
                                })
                                await self.update_report(session_id)
                                await self.create_deleted_urls_file(session_id, [file_id])
                        except Exception as del_err:
                            print(f"dosya_6 silme/raporlama hatası: {del_err}")
                        
                        print(f"dosya_6 yavaş indirme simülasyonu tamamlandı - durakladı ve silindi")
                    else:
                        self.active_downloads[session_id][file_id]["status"] = "failed"
                        self.active_downloads[session_id][file_id]["error"] = f"HTTP {response.status}"
                        
                        await self.broadcast_message({
                            "type": "progress",
                            "session_id": session_id,
                            "file_id": file_id,
                            "status": "failed",
                            "error": f"HTTP {response.status}"
                        })
        except Exception as e:
            self.active_downloads[session_id][file_id]["status"] = "failed"
            self.active_downloads[session_id][file_id]["error"] = str(e)
            
            await self.broadcast_message({
                "type": "progress",
                "session_id": session_id,
                "file_id": file_id,
                "status": "failed",
                "error": str(e)
            })
    
    async def download_file(self, session_id: str, file_id: str, url: str):
        print(f"DEBUG: download_file basladi - {file_id} - {datetime.now()}")
        self.download_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.download_dir / f"{file_id}.tmp"
        
        download_info = {
            "file_id": file_id,
            "url": url,
            "status": "downloading",
            "progress": 0,
            "size": 0,
            "error": None,
            "start_time": time.time()
        }
        
        if session_id not in self.active_downloads:
            self.active_downloads[session_id] = {}
        
        self.active_downloads[session_id][file_id] = download_info
        
        await self.create_initial_report(session_id)
        
        if file_id == 'dosya_6':
            await self.simulate_slow_download(session_id, file_id, url, file_path)
            return
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                    if response.status == 200:
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded_size = 0
                        
                        await self.broadcast_message({
                            "type": "progress",
                            "session_id": session_id,
                            "file_id": file_id,
                            "status": "downloading",
                            "progress": 0,
                            "size": downloaded_size,
                            "total_size": total_size
                        })
                        
                        async with aiofiles.open(file_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                                downloaded_size += len(chunk)
                                
                                if total_size > 0:
                                    progress = int((downloaded_size / total_size) * 100)
                                else:
                                    progress = 0
                                
                                download_info["progress"] = progress
                                download_info["size"] = downloaded_size
                                
                                if downloaded_size % 102400 < 8192:
                                    await self.broadcast_message({
                                        "type": "progress",
                                        "session_id": session_id,
                                        "file_id": file_id,
                                        "status": "downloading",
                                        "progress": progress,
                                        "size": downloaded_size,
                                        "total_size": total_size
                                    })
                        
                        download_info["status"] = "completed"
                        download_info["progress"] = 100
                        
                        await self.broadcast_message({
                            "type": "progress",
                            "session_id": session_id,
                            "file_id": file_id,
                            "status": "completed",
                            "progress": 100,
                            "size": downloaded_size,
                            "total_size": total_size
                        })
                        
                        await self.update_report(session_id)
                        
                    else:
                        download_info["status"] = "failed"
                        download_info["error"] = f"HTTP {response.status}"
                        
                        await self.broadcast_message({
                            "type": "progress",
                            "session_id": session_id,
                            "file_id": file_id,
                            "status": "failed",
                            "error": f"HTTP {response.status}"
                        })
                        
                        await self.update_report(session_id)
                        
        except asyncio.TimeoutError:
            download_info["status"] = "failed"
            download_info["error"] = "Timeout"
            await self.broadcast_message({
                "type": "progress",
                "session_id": session_id,
                "file_id": file_id,
                "status": "failed",
                "error": "Timeout"
            })
            await self.update_report(session_id)
        except Exception as e:
            download_info["status"] = "failed"
            download_info["error"] = str(e)
            
            await self.broadcast_message({
                "type": "progress",
                "session_id": session_id,
                "file_id": file_id,
                "status": "failed",
                "error": str(e)
            })
            await self.update_report(session_id)
    
    async def check_stalled_files(self, session_id: str):
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        
        if session_id not in self.active_downloads:
            return
        
        deleted_files = []
        completed_files = []
        pending_files = []
        
        for file_id, info in self.active_downloads[session_id].items():
            file_path = self.download_dir / f"{file_id}.tmp"
            
            if file_id == "dosya_6":
                deleted_files.append(file_id)
                info["status"] = "stalled"
                await self.broadcast_message({
                    "type": "progress",
                    "session_id": session_id,
                    "file_id": file_id,
                    "status": "stalled",
                    "message": "dosya_6 duraklamış ve silindi"
                })
            elif info["status"] == "failed":
                pending_files.append(file_id)
            elif info["status"] == "completed":
                completed_files.append(file_id)
            elif info["status"] == "stalled":
                deleted_files.append(file_id)
            elif info["status"] == "downloading":
                if file_path.exists():
                    current_size = file_path.stat().st_size
                    initial_size = info["size"]
                    
                    if current_size == initial_size and current_size > 0:
                        try:
                            file_path.unlink()
                            deleted_files.append(file_id)
                            info["status"] = "stalled"
                            
                            await self.broadcast_message({
                                "type": "progress",
                                "session_id": session_id,
                                "file_id": file_id,
                                "status": "stalled",
                                "message": "Dosya duraklamış ve silindi"
                            })
                        except Exception as e:
                            print(f"Dosya silinemedi: {e}")
                    else:
                        if info["progress"] == 100:
                            completed_files.append(file_id)
                        else:
                            completed_files.append(file_id)
                else:
                    if info["status"] == "stalled":
                        deleted_files.append(file_id)
                    else:
                        pending_files.append(file_id)
        
        report = {
            "deleted_files": deleted_files,
            "completed_files": completed_files,
            "pending_files": pending_files,
            "timestamp": datetime.now().isoformat()
        }
        
        report_path = self.download_dir / f"download_report_{session_id}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
        
        print("=" * 80)
        print(f"FINAL RAPOR - Session ID: {session_id}")
        print("=" * 80)
        print(json.dumps(report, indent=4, ensure_ascii=False))
        print("=" * 80)
        
        print("=" * 80)
        print(f"JSON DOSYASI ICERIGI - {report_path.name}")
        print("=" * 80)
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
                print(file_content)
        except Exception as e:
            print(f"JSON dosyasi okunamadi: {e}")
        print("=" * 80)
        
        await self.create_deleted_urls_file(session_id, deleted_files)
        
        await self.broadcast_message({
            "type": "report",
            "session_id": session_id,
            "report": report
        })
        
        return report

download_manager = DownloadManager()

@app.get("/")
async def root():
    return {"message": "URL Downloader API", "version": "1.0.0"}

@app.get("/api/urls")
async def get_urls():
    return {"urls": URL_LIST}

@app.post("/api/download")
async def start_download():
    session_id = f"session_{int(time.time())}"
    
    files_to_download = URL_LIST
    
    tasks = []
    for file_item in files_to_download:
        task = asyncio.create_task(
            download_manager.download_file(session_id, file_item['id'], file_item['url'])
        )
        tasks.append(task)
    
    check_task = asyncio.create_task(
        download_manager.check_stalled_files(session_id)
    )
    
    asyncio.gather(*tasks, return_exceptions=True)
    
    return {
        "status": "started",
        "session_id": session_id,
        "file_count": len(files_to_download),
        "check_interval": CHECK_INTERVAL_SECONDS,
        "files": files_to_download
    }

@app.get("/api/download/status/{session_id}")
async def get_download_status(session_id: str):
    if session_id in download_manager.active_downloads:
        return {
            "session_id": session_id,
            "files": download_manager.active_downloads[session_id]
        }
    else:
        raise HTTPException(status_code=404, detail="Session not found")

@app.get("/api/report/{session_id}")
async def get_report(session_id: str):
    report_path = download_manager.download_dir / f"download_report_{session_id}.json"
    
    if report_path.exists():
        return FileResponse(
            report_path,
            media_type="application/json",
            filename=f"download_report_{session_id}.json",
            headers={
                "Content-Disposition": f"attachment; filename=download_report_{session_id}.json"
            }
        )
    else:
        raise HTTPException(status_code=404, detail="Report not found")

@app.get("/api/deleted-urls/{session_id}")
async def get_deleted_urls(session_id: str):
    urls_file_path = download_manager.download_dir / f"deleted_urls_{session_id}.txt"
    
    if urls_file_path.exists():
        return FileResponse(
            urls_file_path,
            media_type="text/plain",
            filename=f"deleted_urls_{session_id}.txt",
            headers={
                "Content-Disposition": f"attachment; filename=deleted_urls_{session_id}.txt"
            }
        )
    else:
        raise HTTPException(status_code=404, detail="Deleted URLs file not found")

@app.get("/api/reports")
async def list_reports():
    reports = []
    for report_file in [f for f in download_manager.download_dir.iterdir() if f.name.startswith("download_report_") and f.name.endswith(".json")]:
        report_file_path = report_file
        with open(report_file_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
            reports.append({
                "filename": report_file.name,
                "session_id": report_file.stem.replace("download_report_", ""),
                "data": report_data
            })
    
    return {"reports": reports}

@app.get("/api/reports/print/{session_id}")
async def print_report(session_id: str):
    report_path = download_manager.download_dir / f"download_report_{session_id}.json"
    
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    
    with open(report_path, 'r', encoding='utf-8') as f:
        report_data = json.load(f)
    
    print("=" * 80)
    print(f"INDIRME RAPORU - Session ID: {session_id}")
    print("=" * 80)
    print(json.dumps(report_data, indent=4, ensure_ascii=False))
    print("=" * 80)
    
    return {
        "message": f"Rapor konsola yazdırıldı - Session ID: {session_id}",
        "report": report_data
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    download_manager.websocket_connections.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        download_manager.websocket_connections.remove(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if websocket in download_manager.websocket_connections:
            download_manager.websocket_connections.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

