import os
import requests
import re
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

def fetch_metadata(item_id):
    url = f"https://gyutto.com/i/item{item_id}"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch page for {item_id}: {response.status_code}")
        return {}

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract title to check if the item is down-sold
    try:
        title_node = soup.select_one('div.parts_Mds01.clearfix h1')
        title = title_node.text.strip() if title_node else ""
    except AttributeError as e:
        print(f"Error parsing metadata for {item_id}: {e}")
        return {}

    # Check if the title contains "エラーが発生しました。" (error message)
    if "エラーが発生しました。" in title:
        return {}  # Item is down-sold, return empty dict

    # Extract other metadata if the item is available
    try:
        cover_node = soup.select_one('div.unit_DojinMainPh a.highslide img')
        cover_url = f"https://gyutto.com{cover_node['src']}" if cover_node else ""

        preview_nodes = soup.select('div.unit_SamplePhSmall a.highslide img')
        preview_images = [f"https://gyutto.com{node['src']}" for node in preview_nodes]

        club_node = soup.select_one('dt:contains("サークル") + dd a')
        club_name = club_node.text.strip() if club_node else ""

        tags_nodes = soup.select('dt:contains("ジャンル") + dd a')
        tags = [tag.text.strip() for tag in tags_nodes]

        release_node = soup.select_one('dt:contains("配信開始日") + dd')
        release_date = release_node.text.strip() if release_node else ""

        # Extract description
        description_node = soup.select('div.unit_DetailSummary.clearfix p, div.unit_DetailSummary.clearfix div.ItemLead')
        description = description_node[0].text.strip() if description_node else ""

    except AttributeError as e:
        print(f"Error parsing metadata for {item_id}: {e}")
        return {}

    return {
        "number": f"GYUTTO-{item_id}",
        "label": club_name,
        "title": title,
        "cover_url": cover_url,
        "preview_images": preview_images,
        "tags": tags,
        "release_date": release_date,
        "description": description  # Add description to metadata
    }


def download_file(url, save_path):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(save_path, 'wb') as file:
            for chunk in response.iter_content(1024):
                file.write(chunk)
    else:
        print(f"Failed to download {url}: {response.status_code}")

def sanitize_filename(filename):
    invalid_chars = r'[<>:"/\\|?*\x00-\x1F]'
    sanitized = re.sub(invalid_chars, '_', filename)
    sanitized = sanitized.replace('/', '_')  # Linux 特殊处理
    sanitized = sanitized.rstrip(' .')  # 刪除結尾的點和空格（Windows 处理）
    sanitized = sanitized.lstrip('.')  # 避免 Linux 隐藏文件问题
    sanitized = sanitized.encode('utf-8')[:220]  # 按 UTF-8 字节截断
    sanitized = sanitized.decode('utf-8', 'ignore')  # 忽略无效字节 限制文件名长度
    return sanitized

# Function to check if the folder contains a valid video file
def contains_video_file(folder_path):
    video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv']
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if any(file.lower().endswith(ext) for ext in video_extensions):
                return True, os.path.join(root, file)  # Return the video file path if found
    return False, None

def create_nfo(metadata, folder_path):
    if not metadata:
        return
    
    # 创建 genre 部分
    tags = list(set(metadata.get("tags", [])))  # 使用 set 去重
    genres = "\n".join([f"    <genre>{genre}</genre>" for genre in tags])

    # 提取年份并移除“年”、“月”、“日”
    release_date = metadata.get("release_date", "")
    #year = re.sub(r'[^\d]', '', release_date)  # 去除非数字字符
    year = re.search(r'(\d{4})', release_date)  # 正则匹配4位数字作为年份
    
    if year:
        year = year.group(1)  # 只取年份部分
    else:
        year = ""  # 如果没有匹配到年份，则为空

    nfo_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<movie>
    <title>{metadata.get("title", "")}</title>
    <year>{year}</year>
{genres}
    <plot>{metadata.get("description", "")}</plot>
    <tagline>{metadata.get("title", "")}</tagline>
    <director>{metadata.get("label", "")}</director>
    <poster>{metadata.get("cover_url", "")}</poster>
</movie>"""

    # Check if a video file is present in the current folder or subfolders
    has_video, video_file_path = contains_video_file(folder_path)
    
    # If video file is found in subfolder, place the nfo in the same folder as the video file
    if has_video:
        nfo_folder = os.path.dirname(video_file_path)
    else:
        nfo_folder = folder_path  # Use the original folder if no video file is found

    # Save the nfo file in the determined folder
    nfo_filename = os.path.join(nfo_folder, "movie.nfo")
    with open(nfo_filename, 'w', encoding='utf-8') as nfo_file:
        nfo_file.write(nfo_content)

def process_folders(base_dir):
    pattern = re.compile(r'^\[?gyutto-?(\d+)\]?(?:\D.*|\d*)?$|^item(\d+)$', re.IGNORECASE)
    
    for folder in os.listdir(base_dir):
        folder_path = os.path.join(base_dir, folder)
        
        if not os.path.isdir(folder_path) or not pattern.match(folder):
            continue

        match = pattern.match(folder)
        if not match:
            continue
        
        # 提取 item ID
        item_id = match.group(1) or match.group(2)
        if not item_id:
            continue

        # Fetch metadata
        metadata = fetch_metadata(item_id)

        # Initialize new_folder_name as empty string
        new_folder_name = ""

        if not metadata:
            # If metadata is empty, just use Gyutto-ID for folder name
            new_folder_name = f"Gyutto-{item_id}"
            cover_url = f"https://image.gyutto.com/data/item_img/{item_id[:-2]}/{item_id}/{item_id}.jpg"
            preview_images = [
                f"https://image.gyutto.com/data/item_img/{item_id[:-2]}/{item_id}/{item_id}_430.jpg",
                f"https://image.gyutto.com/data/item_img/{item_id[:-2]}/{item_id}/{item_id}_431.jpg",
                f"https://image.gyutto.com/data/item_img/{item_id[:-2]}/{item_id}/{item_id}_432.jpg"
            ]
        else:
            # If metadata is available, use the format [Gyutto-ID][label]title
            sanitized_number = sanitize_filename(metadata.get("number", ""))
            sanitized_label = sanitize_filename(metadata.get("label", ""))
            sanitized_title = sanitize_filename(metadata.get("title", ""))
            
            # Construct folder name in the format [Gyutto-ID][label]title
            new_folder_name = f"[{sanitized_number}][{sanitized_label}]{sanitized_title}"
            
            cover_url = metadata.get("cover_url", "")
            preview_images = metadata.get("preview_images", [])

        # Sanitize folder name
        new_folder_name = sanitize_filename(new_folder_name)

        # Download cover and preview images
        if cover_url:
            ext = os.path.splitext(cover_url)[-1]  # 获取文件扩展名
            poster_path = os.path.join(folder_path, f"poster{ext}")  # 动态生成文件名
            download_file(cover_url, poster_path)

        for idx, img_url in enumerate(preview_images):
            ext = os.path.splitext(img_url)[-1]
            download_file(img_url, os.path.join(folder_path, f"backdrop{idx + 1}{ext}"))

        # Rename folder
        new_folder_path = os.path.join(base_dir, new_folder_name)
        try:
            os.rename(folder_path, new_folder_path)
        except Exception as e:
            print(f"Failed to rename {folder_path} to {new_folder_path}: {e}")

        # Generate NFO file in the correct location
        create_nfo(metadata, new_folder_path)

if __name__ == "__main__":
    #文件位置 替换成你要刮削的资料夹文件名，如果是windows要把路径的\换成\\
    base_directory = r"C:\\Users\\用户名\\Desktop\\12345\\python"
    process_folders(base_directory)
