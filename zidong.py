import os
import requests
import re
from datetime import datetime

def get_search_results(base_url, query):
    """使用搜索接口查询商品信息"""
    url = f"{base_url}/v1/movies/search?q={query}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json().get("data", [])
        if data:
            return data[0]  # 选择第一个搜索结果
    print(f"Failed to fetch search results for {query}: {response.status_code}")
    return None

def get_detailed_info(base_url, provider, item_id):
    """使用商品ID和provider查询详细信息"""
    url = f"{base_url}/v1/movies/{provider}/{item_id}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json().get("data", {})
        return data
    print(f"Failed to fetch detailed info for {item_id}: {response.status_code}")
    return None

def download_file(url, save_path):
    """下载文件，支持断点续传"""
    if os.path.exists(save_path):
        print(f"File already exists: {save_path}")
        return
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(save_path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            #print(f"Downloaded {url} to {save_path}")
        else:
            print(f"Failed to download {url}: {response.status_code}")
    except Exception as e:
        print(f"Error downloading {url}: {e}")

def fix_fc2_url(url):
    """修正 FC2 图片 URL，移除无效部分"""
    pattern = r'https://contents-thumbnail2\.fc2\.com/[^/]+/(storage\d+\.contents\.fc2\.com/.+)'
    match = re.match(pattern, url)
    if match:
        return f"https://{match.group(1)}"
    return url  # 如果不匹配，返回原始 URL

def sanitize_filename(filename):
    """清理无效字符，确保文件名合法"""
    invalid_chars = r'[<>:"/\\|?*\x00-\x1F]'
    sanitized = re.sub(invalid_chars, '_', filename)
    sanitized = sanitized.replace('/', '_')  # Linux 特殊处理
    sanitized = sanitized.rstrip(' .')  # 刪除結尾的點和空格（Windows 处理）
    sanitized = sanitized.lstrip('.')  # 避免 Linux 隐藏文件问题
    sanitized = sanitized.encode('utf-8')[:220]  # 按 UTF-8 字节截断
    sanitized = sanitized.decode('utf-8', 'ignore')  # 忽略无效字节 限制文件名长度
    return sanitized

def create_nfo(metadata, folder_path, label, maker, series):
    """创建 nfo 文件，并确保与视频文件位于相同目录中"""
    nfo_filename = os.path.join(folder_path, "movie.nfo")
    
    # 检查目录及其子目录是否存在视频文件
    video_found_path = None
    for root, _, files in os.walk(folder_path):
        if any(f.lower().endswith(('mp4', 'mkv', 'avi', 'mov')) for f in files):
            video_found_path = root  # 找到包含视频文件的目录
            break

    # 如果找到视频文件，将 NFO 文件创建在对应视频文件的目录中
    if video_found_path:
        nfo_filename = os.path.join(video_found_path, "movie.nfo")
    else:
        nfo_filename = os.path.join(folder_path, "movie.nfo")

    # 确保目标目录存在
    os.makedirs(os.path.dirname(nfo_filename), exist_ok=True)

    try:
        # 如果label为空，则使用maker；如果maker也为空，则使用series
        director = label if label else (maker if maker else series)

        plot = metadata.get("summary", "").strip()
        genres = metadata.get("genres", [])
        formatted_genres = "".join([f"    <genre>{genre}</genre>\n" for genre in genres])
        release_date = metadata.get("release_date", "")
        formatted_date = release_date.split('T')[0]  # 提取日期部分

        nfo_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<movie>
    <title>{metadata.get('title', 'Unknown')}</title>
    <number>{metadata.get('number', 'Unknown')}</number>
    <director>{director}</director>
    <year>{formatted_date[:4]}</year>
    <plot>{plot}</plot>
{formatted_genres}    <premiered>{formatted_date}</premiered>
    <tagline>{metadata.get('title', 'Unknown')}</tagline>
    <poster>{metadata.get("cover_url", "")}</poster>
</movie>
"""
        with open(nfo_filename, 'w', encoding='utf-8') as nfo_file:
            nfo_file.write(nfo_content)
        print(f"Created NFO file: {nfo_filename}")
    except Exception as e:
        print(f"Failed to create NFO file for {folder_path}: {e}")


def process_folder(base_url, folder_path):
    """处理资料夹，查询并下载元数据"""
    folder_name = os.path.basename(folder_path)
    
    # 第一步：查询商品ID
    search_result = get_search_results(base_url, folder_name)
    if not search_result:
        return
    
    item_id = search_result.get("id", "")
    provider = search_result.get("provider", "")
    
    # 第二步：获取详细信息
    detailed_info = get_detailed_info(base_url, provider, item_id)
    if not detailed_info:
        return
    
    number = detailed_info.get("number", "")
    label = detailed_info.get("label", "")
    maker = detailed_info.get("maker", "")
    series = detailed_info.get("series", "")
    title = detailed_info.get("title", "")
    cover_url = detailed_info.get("cover_url", "")
    preview_images = detailed_info.get("preview_images", [])
    
    # 如果label为空，则使用maker；如果maker也为空，则使用series
    if not label:
        label = maker if maker else series
    
    # 仅当 provider 为 FC2 时修正 URL
    if provider == "FC2":
        cover_url = fix_fc2_url(cover_url)
        preview_images = [fix_fc2_url(img) for img in preview_images]
    
    # 下载封面图
    if cover_url:
        ext = os.path.splitext(cover_url)[-1]  # 获取文件扩展名
        poster_path = os.path.join(folder_path, f"poster{ext}")  # 动态生成文件名
        download_file(cover_url, poster_path)
    
    # 下载介绍图片
    for idx, img_url in enumerate(preview_images):
        ext = os.path.splitext(img_url)[-1]
        download_file(img_url, os.path.join(folder_path, f"backdrop{idx+1}{ext}"))
    
    # 清理元数据中的标签和标题
    sanitized_label = sanitize_filename(label)
    sanitized_title = sanitize_filename(title)
    
    # 重命名文件夹
    new_folder_name = f"[{sanitize_filename(number)}][{sanitized_label}]{sanitized_title}"
    new_folder_name = sanitize_filename(new_folder_name)
    new_folder_path = os.path.join(os.path.dirname(folder_path), new_folder_name)
    
    try:
        os.rename(folder_path, new_folder_path)
        print(f"Renamed folder to {new_folder_name}")
    except Exception as e:
        print(f"Failed to rename {folder_path} to {new_folder_path}: {e}")
    
    # 创建nfo文件
    create_nfo(detailed_info, new_folder_path, label, maker, series)

if __name__ == "__main__":
    # 文件位置 替换成你要刮削的资料夹文件名，如果是windows要把路径的\换成\\
    base_directory = r"C:\\Users\\用户名\\Desktop\\12345\\python"
    # metatube，把http://10.0.0.189:123 换成你的metatube与端口
    base_url = "http://10.0.0.189:123"
    
    for folder in os.listdir(base_directory):
        folder_path = os.path.join(base_directory, folder)
        
        if os.path.isdir(folder_path):
            process_folder(base_url, folder_path)
