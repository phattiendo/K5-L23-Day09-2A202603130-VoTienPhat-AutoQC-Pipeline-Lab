"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp."""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    lf_cfg = cfg["label_format"]
    overflow_tol = lf_cfg["overflow_tol"]
    min_box_px = lf_cfg["min_box_px"]
    max_box_frac = lf_cfg["max_box_frac"]
    dup_box_iou = lf_cfg["dup_box_iou"]
    n_classes = len(ds.classes)

    issues = []
    for img_path in ds.image_files():
        stem = img_path.stem
        lines = ds.read_label_lines(stem)
        if lines is None:
            continue

        img_sz = ds.image_size(stem)
        seen_boxes = []  # (cls_id, (cx, cy, w, h))

        for line_no, text in lines:
            try:
                cls_id, cx, cy, w, h = parse_yolo_line(text)
            except ValueError as e:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem, f"sai định dạng: {e}", line=line_no))
                continue

            if not (0 <= cls_id < n_classes):
                issues.append(Issue("label_format", ERROR, "BAD_CLASS_ID", stem, f"id lớp {cls_id} ngoài 0..{n_classes - 1}", line=line_no))
                continue

            if w <= 0 or h <= 0:
                issues.append(Issue("label_format", ERROR, "BOX_ZERO", stem, f"box rỗng w={w}, h={h}", line=line_no))
                continue

            x1, y1 = cx - w / 2.0, cy - h / 2.0
            x2, y2 = cx + w / 2.0, cy + h / 2.0
            overflow = max(0.0, -x1, -y1, x2 - 1.0, y2 - 1.0)
            if overflow > overflow_tol:
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "BOX_OUT_OF_IMAGE",
                        stem,
                        f"box tràn ảnh {overflow:.4f}",
                        line=line_no,
                        extra={"overflow": round(overflow, 6)},
                    )
                )

            cur_box = (cx, cy, w, h)
            is_dup = any(
                prev_cls == cls_id and iou_xywh(prev_box, cur_box) > dup_box_iou
                for prev_cls, prev_box in seen_boxes
            )
            if is_dup:
                issues.append(Issue("label_format", ERROR, "DUP_BOX", stem, "box trùng lặp cùng lớp", line=line_no))
            seen_boxes.append((cls_id, cur_box))

            if img_sz is not None:
                img_w, img_h = img_sz
                short_side = min(w * img_w, h * img_h)
                if short_side < min_box_px:
                    issues.append(
                        Issue(
                            "label_format",
                            WARN,
                            "BOX_TINY",
                            stem,
                            f"box quá nhỏ ({short_side:.1f}px < {min_box_px}px)",
                            line=line_no,
                        )
                    )

            if w * h > max_box_frac:
                issues.append(
                    Issue(
                        "label_format",
                        WARN,
                        "BOX_HUGE",
                        stem,
                        f"box quá lớn ({w * h:.2f} > {max_box_frac})",
                        line=line_no,
                    )
                )

    return issues
