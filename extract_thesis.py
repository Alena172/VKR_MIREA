import json

with open('C:/Users/Alena/.claude/projects/d--VKR-VKR-V3-Curs/1cac9135-d253-424c-beed-be26ac5aa8be.jsonl', 'r', encoding='utf-8') as f:
    lines = f.readlines()

def find_text(obj):
    if isinstance(obj, dict):
        if 'text' in obj and isinstance(obj['text'], str) and 'Количество листингов' in obj['text']:
            return obj['text']
        for v in obj.values():
            r = find_text(v)
            if r:
                return r
    elif isinstance(obj, list):
        for item in obj:
            r = find_text(item)
            if r:
                return r
    return None

for line in lines:
    line = line.strip()
    if not line:
        continue
    if 'Количество листингов' not in line:
        continue
    try:
        data = json.loads(line)
        text = find_text(data)
        if text:
            with open('d:/VKR/VKR_V3_Curs/thesis_section3_original.txt', 'w', encoding='utf-8') as out:
                out.write(text)
            print(f"Found and saved, length={len(text)}")
            break
    except Exception as e:
        print(f"Parse error: {e}")
        break
