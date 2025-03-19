import os
import requests
import re
from datetime import datetime

# 开关变量：是否重命名文件夹
# True 开启 False 关闭
RENAME_FOLDERS = True
# 文件位置 替换成你要刮削的资料夹文件名，如果是windows要把路径的\换成\\
base_directory = r"C:\\Users\\用户名\\Desktop\\12345\\python"
# metatube，把http://10.0.0.189:123 换成你的metatube与端口
metatube_service_url = "http://10.0.0.189:123/v1/movies/Getchu"

def get_metadata(base_url, item_id):
    url = f"{base_url}/{item_id}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get("data", {})
    else:
        print(f"Failed to fetch metadata for {item_id}: {response.status_code}")
        return {}

def download_file(url, save_path):
    if os.path.exists(save_path):
        print(f"File already exists, skipping download: {save_path}")
        return
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(save_path, 'wb') as file:
            for chunk in response.iter_content(1024):
                file.write(chunk)
    else:
        print(f"Failed to download {url}: {response.status_code}")

def get_special_image_urls(item_id):
    base_id = item_id[:-2] if len(item_id) > 2 else item_id
    base_path = f"https://dl.getchu.com/data/item_img/{base_id}/{item_id}/"
    cover_url = f"{base_path}{item_id}top.jpg"
    preview_images = [f"{base_path}{item_id}_{i}.jpg" for i in range(2977, 2980)]
    return cover_url, preview_images

def sanitize_filename(filename):
    invalid_chars = r'[<>:"/\\|?*\x00-\x1F]'
    sanitized = re.sub(invalid_chars, '_', filename)
    sanitized = sanitized.replace('/', '_')  # Linux 特殊处理
    sanitized = sanitized.rstrip(' .')  # 刪除結尾的點和空格（Windows 处理）
    sanitized = sanitized.lstrip('.')  # 避免 Linux 隐藏文件问题
    sanitized = sanitized.encode('utf-8')[:255]  # 按 UTF-8 字节截断
    sanitized = sanitized.decode('utf-8', 'ignore')  # 忽略无效字节 限制文件名长度
    return sanitized

def format_date(release_date):
    try:
        date = datetime.fromisoformat(release_date.split('T')[0])
        return date.strftime('%Y-%m-%d')
    except ValueError:
        return ""

def create_nfo(metadata, folder_path, item_id):
    # 存储所有包含视频文件的目录
    video_dirs = []

    # 遍历文件夹查找视频文件
    for root, _, files in os.walk(folder_path):
        if any(f.lower().endswith(('mp4', 'mkv', 'avi', 'mov')) for f in files):
            video_dirs.append(root)

    # 如果找到多个包含视频文件的目录
    if video_dirs:
        for video_dir in video_dirs:
            nfo_filename = os.path.join(video_dir, "movie.nfo")
            if os.path.exists(nfo_filename):
                print(f"NFO file already exists, skipping creation: {nfo_filename}")
                continue
            write_nfo_file(metadata, nfo_filename)
    else:
        # 如果没有视频文件，在根目录生成NFO
        nfo_filename = os.path.join(folder_path, "movie.nfo")
        if os.path.exists(nfo_filename):
            print(f"NFO file already exists, skipping creation: {nfo_filename}")
            return
        write_nfo_file(metadata, nfo_filename)

def write_nfo_file(metadata, nfo_filename):
    try:
        os.makedirs(os.path.dirname(nfo_filename), exist_ok=True)
        with open(nfo_filename, 'w', encoding='utf-8') as nfo_file:
            plot = metadata.get("summary", "").strip()
            genres = metadata.get("genres", [])
            formatted_genres = "".join([f"    <genre>{genre}</genre>\n" for genre in genres])
            release_date = metadata.get("release_date", "")
            formatted_date = format_date(release_date)

            nfo_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<movie>
    <title>{metadata.get('title', '')}</title>
    <number>{metadata.get('number', '')}</number>
    <director>{metadata.get('label', '')}</director>
    <year>{formatted_date[:4]}</year>
    <plot>{plot}</plot>
{formatted_genres}    <premiered>{formatted_date}</premiered>
    <tagline>{metadata.get('title', '')}</tagline>
    <poster>{metadata.get("cover_url", "")}</poster>
</movie>
"""
            nfo_file.write(nfo_content)
        print(f"Created NFO file: {nfo_filename}")
    except Exception as e:
        print(f"Failed to create NFO file for {nfo_filename}: {e}")


def process_folders(base_dir, metatube_url):
    for folder in os.listdir(base_dir):
        folder_path = os.path.join(base_dir, folder)

        if not os.path.isdir(folder_path):
            continue

        item_id_match = re.search(r'(?:item(\d+)|\[(?:GETCHU-)?(\d+)\])', folder)
        if item_id_match:
            item_id = item_id_match.group(1) or item_id_match.group(2)
        else:
            print(f"Failed to extract item_id from folder name: {folder}")
            continue

        metadata = get_metadata(metatube_url, item_id)
        if metadata:
            number = metadata.get("number", "")
            label = metadata.get("label", "")
            title = metadata.get("title", "")
            cover_url = metadata.get("cover_url", "")
            preview_images = metadata.get("preview_images", [])
            sanitized_number = sanitize_filename(number)
            sanitized_label = sanitize_filename(label)
            sanitized_title = sanitize_filename(title)
        else:
            cover_url, preview_images = get_special_image_urls(item_id)

        if cover_url:
            ext = os.path.splitext(cover_url)[-1]  # 获取文件扩展名
            poster_path = os.path.join(folder_path, f"poster{ext}")
            download_file(cover_url, poster_path)

        for idx, img_url in enumerate(preview_images):
            ext = os.path.splitext(img_url)[-1]
            preview_path = os.path.join(folder_path, f"backdrop{idx+1}{ext}")
            download_file(img_url, preview_path)

        
        if metadata:
            create_nfo(metadata, folder_path, item_id)

        if RENAME_FOLDERS and metadata:
            new_folder_name = f"[{sanitized_number}][{sanitized_label}]{sanitized_title}"
            new_folder_name = sanitize_filename(new_folder_name)
            new_folder_path = os.path.join(base_dir, new_folder_name)

            try:
                os.rename(folder_path, new_folder_path)
                print(f"Renamed folder: {folder_path} -> {new_folder_path}")
            except Exception as e:
                print(f"Failed to rename {folder_path} to {new_folder_path}: {e}")

if __name__ == "__main__":
    process_folders(base_directory, metatube_service_url)

