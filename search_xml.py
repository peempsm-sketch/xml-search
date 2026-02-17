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

    # ใส่ quote ให้ key เฉพาะหลัง { หรือ , เท่านั้น
    obj = re.sub(r'(?<=\{|,)\s*(\w+)\s*:', r'"\1":', obj)

    # แปลง ' -> "
    obj = obj.replace("'", '"')

    return json.loads(obj)


def file_matches_multi(xml_path, conditions, mode="AND", case_sensitive=True):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

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
    mode = config.get("mode", "AND")

    if "conditions" in config and isinstance(config["conditions"], list) and config["conditions"]:
        return mode, config["conditions"]

    search = config.get("search", {})
    if isinstance(search, dict) and search.get("key") and search.get("value"):
        return mode, [{"key": search["key"], "value": search["value"]}]

    raise ValueError("config.js ต้องมี conditions[] หรือ search.key/search.value")


def unique_destination_path(output_dir: str, src_path: str) -> str:
    base = os.path.basename(src_path)
    name, ext = os.path.splitext(base)
    dst = os.path.join(output_dir, base)

    if not os.path.exists(dst):
        return dst

    i = 2
    while True:
        dst2 = os.path.join(output_dir, f"{name}_{i}{ext}")
        if not os.path.exists(dst2):
            return dst2
        i += 1


def to_abs(base_dir: str, p: str) -> str:
    return p if os.path.isabs(p) else os.path.abspath(os.path.join(base_dir, p))


def main():
    config = load_config_from_js("config.js")
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # ✅ รองรับทั้ง inputDir และ inputDirs
    input_dirs = []
    if "inputDirs" in config and isinstance(config["inputDirs"], list) and config["inputDirs"]:
        input_dirs = [to_abs(base_dir, d) for d in config["inputDirs"]]
    elif "inputDir" in config and isinstance(config["inputDir"], str) and config["inputDir"].strip():
        input_dirs = [to_abs(base_dir, config["inputDir"])]
    else:
        raise ValueError("config.js ต้องมี inputDir (string) หรือ inputDirs (array)")

    # outputDir
    if "outputDir" not in config:
        raise ValueError("config.js ต้องมี outputDir")
    output_dir = to_abs(base_dir, config["outputDir"])

    case_sensitive = config.get("caseSensitive", True)
    stop_after_first = config.get("stopAfterFirstMatch", True)

    mode, conditions = normalize_conditions_from_config(config)

    os.makedirs(output_dir, exist_ok=True)

    # ✅ Debug (พิมพ์ก่อนเริ่มค้นหา จะได้เห็นค่าจริง)


    matched = 0

    # ✅ ไล่ทีละโฟลเดอร์ตามลำดับใน inputDirs
    for input_dir in input_dirs:
        if not os.path.isdir(input_dir):
            print(f"[WARN] ไม่พบโฟลเดอร์: {input_dir}")
            continue

        # ✅ เดินทุกโฟลเดอร์ย่อยด้วย os.walk()
        for root_dir, dirs, filenames in os.walk(input_dir):
            for f in filenames:
                if not f.lower().endswith(".xml"):
                    continue

                file_path = os.path.join(root_dir, f)

                if file_matches_multi(file_path, conditions, mode=mode, case_sensitive=case_sensitive):
                    dst = unique_destination_path(output_dir, file_path)
                    shutil.copy2(file_path, dst)
                    matched += 1
                    print(f"[MATCH] {file_path} -> {dst}")

                    if stop_after_first:
                        print("\nเจอไฟล์แรกแล้ว หยุดการค้นหา (stopAfterFirstMatch=true)")
                        print(f"คัดลอกไว้ที่: {output_dir}")
                        return

    print(f"\nเสร็จแล้ว พบ {matched} ไฟล์")
    print(f"คัดลอกไว้ที่: {output_dir}")


if __name__ == "__main__":
    main()
