import urllib.request
import json
import re
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Helper to clean html
def clean_html(raw_html):
    if not raw_html:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', raw_html)
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'</li>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return text.strip()

def format_size(bytes_sz):
    if not bytes_sz:
        return ""
    if bytes_sz < 1024:
        return f"{bytes_sz} B"
    elif bytes_sz < 1024 * 1024:
        return f"{bytes_sz/1024:.1f} KB"
    else:
        return f"{bytes_sz/(1024*1024):.1f} MB"

# Load download mapping
download_map = {}
if os.path.exists('download_manifest.json'):
    with open('download_manifest.json', 'r', encoding='utf-8') as f:
        manifest = json.load(f)
        for item in manifest:
            save_path = item['save_path'].replace('\\', '/')
            if os.path.exists(save_path):
                sz = os.path.getsize(save_path)
                item['size'] = sz
                item['size_formatted'] = format_size(sz)
                download_map[item['wish_id']] = item

def process_board(board_key, display_name, hashid, original_url, default_color):
    # 1. Fetch Wall info
    w_url = f'https://padlet.com/api/10/walls/{hashid}'
    req = urllib.request.Request(w_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as r:
        w_data = json.loads(r.read().decode('utf-8'))['data']
    wall_id = w_data['id']
    wall_title = w_data['attributes']['title']
    wall_desc = w_data['attributes'].get('description') or ''
    
    # 2. Fetch Sections
    sec_url = f'https://padlet.com/api/10/wall_sections?wall_id={wall_id}'
    req_s = urllib.request.Request(sec_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req_s) as r:
        sec_raw = json.loads(r.read().decode('utf-8'))['data']
        
    sections_order = []
    section_map = {}
    for s in sec_raw:
        s_id = s['id']
        s_title = s['attributes']['title'].strip()
        section_map[s_id] = s_title
        if s_title not in sections_order:
            sections_order.append(s_title)
            
    # 3. Fetch Wishes
    wishes_url = f'https://padlet.com/api/10/wishes?wall_hashid={hashid}'
    req_w = urllib.request.Request(wishes_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req_w) as r:
        wishes_raw = json.loads(r.read().decode('utf-8'))['data']
        
    posts = []
    for item in wishes_raw:
        wid = item['id']
        attr = item['attributes']
        
        sec_id = attr.get('wall_section_id')
        section_name = section_map.get(sec_id, '精選專題')
        
        subject = (attr.get('subject') or attr.get('headline') or '').strip()
        raw_body = attr.get('body') or ''
        plain_body = clean_html(raw_body)
        
        att = attr.get('attachment') or ''
        att_link = attr.get('attachment_link') or {}
        att_title = (att_link.get('title') or '').strip()
        att_url = att_link.get('canonical_url') or att_link.get('display_url') or att or ''
        att_caption = attr.get('attachment_caption') or ''
        permalink = attr.get('permalink') or ''
        
        # Determine local file
        local_file = None
        file_size_formatted = ""
        file_name = ""
        file_ext = ""
        if wid in download_map:
            dl_info = download_map[wid]
            local_file = dl_info['save_path'].replace('\\', '/')
            file_size_formatted = dl_info.get('size_formatted', '')
            file_name = dl_info.get('filename', '')
            file_ext = os.path.splitext(file_name)[1].lower().replace('.', '')
            
        # Display title
        display_title = subject
        if not display_title or display_title == '空白':
            if att_title:
                display_title = att_title
            elif plain_body:
                first_line = plain_body.split('\n')[0][:40]
                display_title = first_line + ('...' if len(plain_body) > 40 else '')
            elif file_name:
                display_title = file_name
            else:
                display_title = '實作資源卡片'
                
        # Copy text
        copy_text = display_title
        if plain_body:
            copy_text += f"\n\n{plain_body}"
        if att_url and not plain_body:
            copy_text += f"\n\n連結：{att_url}"
            
        # Media type detection
        media_type = 'link'
        if local_file:
            if file_ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                media_type = 'image'
            elif file_ext in ['pdf']:
                media_type = 'pdf'
            elif file_ext in ['zip', 'rar', '7z']:
                media_type = 'archive'
            elif file_ext in ['pptx', 'ppt', 'docx', 'doc']:
                media_type = 'document'
            elif file_ext in ['mov', 'mp4', 'webm']:
                media_type = 'video'
            else:
                media_type = 'file'
        elif att_url:
            if any(x in att_url.lower() for x in ['.png', '.jpg', '.jpeg', '.webp']):
                media_type = 'image'
            elif 'youtube.com' in att_url or 'youtu.be' in att_url:
                media_type = 'youtube'
            elif 'canva.com' in att_url or 'canva.link' in att_url:
                media_type = 'canva'
            elif 'gemini.google' in att_url or 'share.gemini' in att_url:
                media_type = 'gemini'
            elif 'padlet.com' in att_url:
                media_type = 'padlet'
            elif 'gamma.app' in att_url:
                media_type = 'gamma'
            elif 'docs.google.com' in att_url or 'forms' in att_url:
                media_type = 'google_form'
            else:
                media_type = 'link'
                
        posts.append({
            'id': wid,
            'section': section_name,
            'title': display_title,
            'original_subject': subject,
            'body_html': raw_body,
            'body_plain': plain_body,
            'has_body': bool(plain_body),
            'attachment_url': att_url,
            'attachment_title': att_title,
            'attachment_caption': att_caption,
            'local_file': local_file,
            'has_local_file': bool(local_file),
            'file_name': file_name,
            'file_size': file_size_formatted,
            'file_ext': file_ext,
            'media_type': media_type,
            'permalink': permalink,
            'copy_text': copy_text,
            'created_at': attr.get('created_at', ''),
            'color': attr.get('color') or default_color
        })
        
    return {
        'board_info': {
            'id': board_key,
            'display_name': display_name,
            'title': wall_title,
            'description': wall_desc,
            'original_url': original_url,
            'total_cards': len(posts),
            'total_sections': len(sections_order),
            'total_files': sum(1 for p in posts if p['local_file'])
        },
        'sections': sections_order,
        'posts': posts
    }

print("Building YaoYao dataset...")
lantern_board = process_board('lantern', '姚老師：AI生圖生活科技應用-AI小宮燈', 'board_Y0KryDdM6gogyPBb', 'https://padlet.com/qianyikeji1/1151108-n-ai-ai-s02566g3xirqh6ikvx88', 'amber')

print("Building Fredcit dataset...")
fredcit_board = process_board('fredcit', '尾翼老師：AI導入生活科技教學實作', 'board_b3MJAj7x1xazyr8l', 'https://padlet.com/fredcit/1151107_-n-ai-s025822gzxae1ezkk444', 'emerald')

all_data = {
    'archive_info': {
        'title': '1151112 花蓮夢N｜生活科技與AI教學實作 雙專題完整典藏系統',
        'subtitle': '夢的N次方 · 花蓮場教師專業成長研習專用教材庫',
        'event_date': '2026-11-12',
        'total_cards': len(lantern_board['posts']) + len(fredcit_board['posts']),
        'total_files': lantern_board['board_info']['total_files'] + fredcit_board['board_info']['total_files'],
        'auth_hash': '5cae49b1fea5b5b969cdc931b8338968940c92309aa2339360cdd5c77be4a4ff'
    },
    'boards': {
        'lantern': lantern_board,
        'fredcit': fredcit_board
    }
}

with open('padlet_archive_data.json', 'w', encoding='utf-8') as f:
    json.dump(all_data, f, ensure_ascii=False, indent=2)

with open('padlet_archive_data.js', 'w', encoding='utf-8') as f:
    f.write(f"// 1151112 花蓮夢N 雙看板完整典藏資料庫\nconst DUAL_PADLET_ARCHIVE = {json.dumps(all_data, ensure_ascii=False, indent=2)};\n")

print("Dataset build complete!")
print(f"Lantern cards: {len(lantern_board['posts'])}, local files: {lantern_board['board_info']['total_files']}")
print(f"Fredcit cards: {len(fredcit_board['posts'])}, local files: {fredcit_board['board_info']['total_files']}")
