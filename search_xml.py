import os
import shutil
import json
import re
import xml.etree.ElementTree as ET

def localname(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def load_config_from_js(path: str):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(
        r'const\s+config\s*=\s*({[\s\S]*?})\s*;?\s*module\.exports',
        content
    )
    if not match:
        raise ValueError("อ่าน config.js ไม่ได้ (ต้องมี const config = {...}; และ module.exports = config;)")

    obj = match.group(1)

    # ลบ trailing comma ก่อน } หรือ ]
    obj = re.sub(r',\s*([}\]])', r'\1', obj)

    # ใส่ quote ให้ key เฉพาะหลัง { หรือ ,
    obj = re.sub(r'(?<=\{|,)\s*(\w+)\s*:', r'"\1":', obj)

    # แปลง ' -> "
    obj = obj.replace("'", '"')

    return json.loads(obj)


def file_matches_multi(xml_path, conditions, mode="AND", case_sensitive=True):
    """
    conditions: [{ "key": "TaxNumber", "value": "xxx" }, ...]
    mode: "AND" or "OR"
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # key -> set(values) ที่พบในไฟล์
        found = {}
        for el in root.iter():
            k = localname(el.tag)
            v = (el.text or "").strip()
            if not v:
                continue

            if not case_sensitive:
                k = k.lower()
                v = v.lower()

            found.setdefault(k, set()).add(v)

        def cond_ok(cond):
            k = cond["key"]
            if not case_sensitive:
                k = k.lower()

            # รองรับทั้ง value เดียว และ values หลายค่า
            if "values" in cond:
                vals = cond["values"]
                if not case_sensitive:
                    vals = [x.lower() for x in vals]
                return any(x in found.get(k, set()) for x in vals)

            v = cond["value"]
            if not case_sensitive:
                v = v.lower()
            return v in found.get(k, set())

        if mode.upper() == "AND":
            return all(cond_ok(c) for c in conditions)
        else:
            return any(cond_ok(c) for c in conditions)

    except Exception as ex:
        print(f"[ERROR] {os.path.basename(xml_path)} -> {ex}")
        return False


def normalize_conditions_from_config(config: dict):
    """
    รองรับ config 2 แบบ:
    1) แบบใหม่:
       mode: "AND"
       conditions: [{key,value}, ...]
    2) แบบเก่า:
       search: { key, value }
       -> แปลงเป็น conditions 1 อันให้
    """
    mode = config.get("mode", "AND")

    if "conditions" in config and isinstance(config["conditions"], list) and config["conditions"]:
        return mode, config["conditions"]

    # fallback แบบเก่า
    search = config.get("search", {})
    if isinstance(search, dict) and search.get("key") and search.get("value"):
        return mode, [{"key": search["key"], "value": search["value"]}]

    raise ValueError("config.js ต้องมี conditions[] หรือ search.key/search.value")


def main():
    config = load_config_from_js("config.js")

    input_dir = config["inputDir"]
    output_dir = config["outputDir"]
    case_sensitive = config.get("caseSensitive", True)

    mode, conditions = normalize_conditions_from_config(config)

    os.makedirs(output_dir, exist_ok=True)

    if not os.path.isdir(input_dir):
        raise ValueError(f"inputDir ไม่ใช่โฟลเดอร์ หรือไม่พบ: {input_dir}")

    files = [
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.lower().endswith(".xml")
    ]

    if not files:
        print("ไม่พบไฟล์ .xml ในโฟลเดอร์ inputDir")
        return

    matched = 0
    for file_path in files:
        if file_matches_multi(file_path, conditions, mode=mode, case_sensitive=case_sensitive):
            shutil.copy2(file_path, os.path.join(output_dir, os.path.basename(file_path)))
            matched += 1
            print(f"[MATCH] {os.path.basename(file_path)}")

    print(f"\nเสร็จแล้ว พบ {matched} ไฟล์")
    print(f"คัดลอกไว้ที่: {output_dir}")


if __name__ == "__main__":
    main()
