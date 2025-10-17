
import asyncio
import aiohttp
import aiofiles
import os
import json
from typing import List, Dict, Any

URL_LIST = [
    {'id': 'dosya_1', 'url': 'https://jsonplaceholder.typicode.com/posts/1'},
    {'id': 'dosya_2', 'url': 'https://jsonplaceholder.typicode.com/posts/2'},
    {'id': 'dosya_3', 'url': 'https://jsonplaceholder.typicode.com/posts/3'},
    {'id': 'dosya_4', 'url': 'https://httpbin.org/status/404'},
    {'id': 'dosya_5', 'url': 'https://httpbin.org/bytes/1024'},
    {'id': 'dosya_6', 'url': 'https://httpbin.org/bytes/512'},
]

DOWNLOAD_DIR = "downloads"
CHECK_INTERVAL_SECONDS = 10

class FileDownloader:
    def __init__(self, download_dir: str = DOWNLOAD_DIR):
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)
        self.download_tasks = {}
        self.file_sizes = {}
        self.download_status = {}
        
    async def download_file(self, file_id: str, url: str) -> None:
        file_path = os.path.join(self.download_dir, f"{file_id}.tmp")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        self.file_sizes[file_id] = 0
                        self.download_status[file_id] = "downloading"
                        
                        async with aiofiles.open(file_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                                self.file_sizes[file_id] = os.path.getsize(file_path)
                        
                        self.download_status[file_id] = "completed"
                        print(f"[OK] {file_id} basariyla indirildi")
                        
                    else:
                        self.download_status[file_id] = "failed"
                        print(f"[ERROR] {file_id} indirilemedi - HTTP {response.status}")
                        
        except Exception as e:
            self.download_status[file_id] = "failed"
            print(f"[ERROR] {file_id} indirme hatasi: {str(e)}")
    
    async def start_downloads(self, url_list: List[Dict[str, str]]) -> None:
        print("Indirme islemleri baslatiliyor...")
        
        tasks = []
        for file_info in url_list:
            file_id = file_info['id']
            url = file_info['url']
            
            task = asyncio.create_task(self.download_file(file_id, url))
            tasks.append(task)
            self.download_tasks[file_id] = task
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def check_file_status(self) -> Dict[str, List[str]]:
        print(f"\n{CHECK_INTERVAL_SECONDS} saniye sonra durum kontrolu yapiliyor...")
        
        deleted_files = []
        completed_files = []
        pending_files = []
        
        for file_id in self.download_status:
            file_path = os.path.join(self.download_dir, f"{file_id}.tmp")
            
            if self.download_status[file_id] == "failed":
                pending_files.append(file_id)
                print(f"[ERROR] {file_id} - Indirilemedi")
                
            elif self.download_status[file_id] == "completed":
                completed_files.append(file_id)
                print(f"[OK] {file_id} - Basariyla tamamlandi")
                
            elif self.download_status[file_id] == "downloading":
                if os.path.exists(file_path):
                    current_size = os.path.getsize(file_path)
                    initial_size = self.file_sizes.get(file_id, 0)
                    
                    if current_size == initial_size and current_size > 0:
                        os.remove(file_path)
                        deleted_files.append(file_id)
                        print(f"[DELETED] {file_id} - Duraklamis, silindi")
                    elif current_size > initial_size:
                        completed_files.append(file_id)
                        print(f"[DOWNLOADING] {file_id} - Hala indiriliyor")
                    else:
                        pending_files.append(file_id)
                        print(f"[ERROR] {file_id} - Dosya bulunamadi")
                else:
                    pending_files.append(file_id)
                    print(f"[ERROR] {file_id} - Dosya bulunamadi")
        
        return {
            "deleted_files": deleted_files,
            "completed_files": completed_files,
            "pending_files": pending_files
        }
    
    def generate_report(self, status_result: Dict[str, List[str]]) -> str:
        report = {
            "deleted_files": status_result["deleted_files"],
            "completed_files": status_result["completed_files"],
            "pending_files": status_result["pending_files"]
        }
        
        return json.dumps(report, indent=4, ensure_ascii=False)

async def main():
    print("=" * 60)
    print("URL'den Dosya Indirme ve Durum Kontrol Uygulamasi")
    print("=" * 60)
    
    downloader = FileDownloader()
    
    await downloader.start_downloads(URL_LIST)
    
    print(f"\n{CHECK_INTERVAL_SECONDS} saniye bekleniyor...")
    await asyncio.sleep(CHECK_INTERVAL_SECONDS)
    
    status_result = downloader.check_file_status()
    
    print("\n" + "=" * 60)
    print("RAPOR")
    print("=" * 60)
    report = downloader.generate_report(status_result)
    print(report)
    
    report_path = os.path.join(downloader.download_dir, "download_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\nRapor dosyaya kaydedildi: {report_path}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nUygulama kullanici tarafindan durduruldu.")
    except Exception as e:
        print(f"\nUygulama hatasi: {str(e)}")

