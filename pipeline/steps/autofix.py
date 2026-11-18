"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN."""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_IMG_PREFIXES = ("DUP_IMAGE_", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE")


def fix(ds, issues, cfg):
    fixes = []
    err_issues = [iss for iss in issues if iss.severity == ERROR]

    removed_stems = set()
    # 1. Xử lý xoá ảnh hỏng / trùng / rò rỉ trước
    for iss in err_issues:
        if iss.code.startswith(REMOVE_IMG_PREFIXES):
            stem = iss.image
            if stem in removed_stems:
                continue
            removed_stems.add(stem)
            img_p = ds.image_path(stem)
            lbl_p = ds.label_path(stem)
            if img_p and img_p.exists():
                img_p.unlink()
            if lbl_p and lbl_p.exists():
                lbl_p.unlink()
            fixes.append(
                {
                    "image": stem,
                    "line": "",
                    "action": "remove_image",
                    "before": stem,
                    "after": "(đã xoá ảnh và nhãn)",
                }
            )

    # 2. Xử lý BAD_CLASS_NAME (data.yaml)
    renamed_yaml = False
    for iss in err_issues:
        if iss.code == "BAD_CLASS_NAME" and not renamed_yaml:
            renamed_yaml = True
            old_names = ds.yaml_names()
            data = {}
            if ds.yaml_path.exists():
                data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
            data["names"] = list(ds.classes)
            data["nc"] = len(ds.classes)
            ds.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
            fixes.append(
                {
                    "image": iss.image,
                    "line": "",
                    "action": "rename_classes",
                    "before": str(old_names),
                    "after": str(list(ds.classes)),
                }
            )

    # 3. Xử lý MISSING_LABEL_FILE
    seen_missing = set()
    for iss in err_issues:
        if iss.code == "MISSING_LABEL_FILE":
            stem = iss.image
            if stem in removed_stems or stem in seen_missing:
                continue
            seen_missing.add(stem)
            fixes.append(
                {
                    "image": stem,
                    "line": "",
                    "action": "needs_label",
                    "before": "(không có file)",
                    "after": "chuyển người gán",
                }
            )

    # 4. Gom lỗi theo từng file nhãn (drop_line thắng clip_box)
    line_ops = defaultdict(dict)  # stem -> {line_no: "drop" | "clip"}
    for iss in err_issues:
        stem = iss.image
        if stem in removed_stems or iss.line is None:
            continue
        if iss.code in DROP_CODES:
            line_ops[stem][iss.line] = "drop"
        elif iss.code == "BOX_OUT_OF_IMAGE":
            if line_ops[stem].get(iss.line) != "drop":
                line_ops[stem][iss.line] = "clip"

    for stem, ops in line_ops.items():
        lbl_p = ds.label_path(stem)
        if not lbl_p.exists():
            continue
        raw_lines = lbl_p.read_text(encoding="utf-8", errors="replace").splitlines()
        new_lines = []
        changed = False

        for idx, raw_ln in enumerate(raw_lines, 1):
            op = ops.get(idx)
            if op is None:
                new_lines.append(raw_ln)
                continue

            if op == "drop":
                changed = True
                fixes.append(
                    {
                        "image": stem,
                        "line": idx,
                        "action": "drop_line",
                        "before": raw_ln.strip(),
                        "after": "",
                    }
                )
            elif op == "clip":
                try:
                    cls_id, cx, cy, w, h = parse_yolo_line(raw_ln)
                except ValueError:
                    changed = True
                    fixes.append(
                        {
                            "image": stem,
                            "line": idx,
                            "action": "drop_line",
                            "before": raw_ln.strip(),
                            "after": "",
                        }
                    )
                    continue

                x1 = max(0.0, min(1.0, cx - w / 2.0))
                y1 = max(0.0, min(1.0, cy - h / 2.0))
                x2 = max(0.0, min(1.0, cx + w / 2.0))
                y2 = max(0.0, min(1.0, cy + h / 2.0))
                nw, nh = x2 - x1, y2 - y1

                if nw <= 0.0 or nh <= 0.0:
                    changed = True
                    fixes.append(
                        {
                            "image": stem,
                            "line": idx,
                            "action": "drop_line",
                            "before": raw_ln.strip(),
                            "after": "",
                        }
                    )
                else:
                    ncx, ncy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                    after_str = f"{cls_id} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}"
                    if after_str != raw_ln.strip():
                        changed = True
                        fixes.append(
                            {
                                "image": stem,
                                "line": idx,
                                "action": "clip_box",
                                "before": raw_ln.strip(),
                                "after": after_str,
                            }
                        )
                    new_lines.append(after_str)

        if changed:
            text_out = "\n".join(new_lines) + ("\n" if new_lines else "")
            lbl_p.write_text(text_out, encoding="utf-8")

    return fixes
