"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l)."""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    so_cfg = cfg["second_opinion"]
    conf_thr = so_cfg["conf"]
    min_area_px = so_cfg["min_area_px"]
    fp_conf = so_cfg["fp_conf"]
    iou_missing = so_cfg["iou_missing"]
    iou_match = so_cfg["iou_match"]
    iou_loose = so_cfg["iou_loose"]
    n_classes = len(ds.classes)

    issues = []

    for img_path in ds.image_files():
        stem = img_path.stem
        if stem not in preds:
            continue
        raw_lines = ds.read_label_lines(stem)
        if raw_lines is None:
            continue

        img_sz = ds.image_size(stem)
        img_w, img_h = img_sz if img_sz is not None else (1, 1)

        # Lấy các dòng nhãn hợp lệ kèm số dòng gốc
        valid_gt = []  # (line_no, cls_id, (cx, cy, w, h))
        for line_no, text in raw_lines:
            try:
                cls_id, cx, cy, w, h = parse_yolo_line(text)
            except ValueError:
                continue
            if 0 <= cls_id < n_classes and w > 0 and h > 0:
                valid_gt.append((line_no, cls_id, (cx, cy, w, h)))

        img_preds = preds[stem]

        # 1. Kiểm tra MISSING / LOOSE_BOX / WRONG_CLASS theo thứ tự dự đoán trong preds[stem]
        for pred in img_preds:
            p_cls, p_conf, pcx, pcy, pw, ph = pred
            p_cls = int(p_cls)
            if p_conf < conf_thr:
                continue
            if (pw * img_w) * (ph * img_h) < min_area_px:
                continue

            p_box = (pcx, pcy, pw, ph)
            cands = []
            for _, g_cls, g_box in valid_gt:
                iou = iou_xywh(p_box, g_box)
                if iou >= iou_missing:
                    cands.append((iou, g_cls))

            if not cands:
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_MISSING",
                        stem,
                        f"model phát hiện lớp {p_cls} (conf={p_conf:.2f}) nhưng nhãn không có",
                        extra={"conf": round(float(p_conf), 4), "pred_cls": p_cls},
                    )
                )
                continue

            same_cls_ious = [iou for iou, g_cls in cands if g_cls == p_cls]
            if same_cls_ious:
                best_same = max(same_cls_ious)
                if best_same < iou_loose:
                    issues.append(
                        Issue(
                            "second_opinion",
                            WARN,
                            "POSSIBLE_LOOSE_BOX",
                            stem,
                            f"box nhãn lớp {p_cls} lệch/lỏng so với model (IoU={best_same:.2f} < {iou_loose})",
                            extra={"conf": round(float(p_conf), 4), "iou": round(float(best_same), 4)},
                        )
                    )
            else:
                best_diff_iou, best_diff_cls = max(cands, key=lambda x: x[0])
                if best_diff_iou >= iou_match:
                    issues.append(
                        Issue(
                            "second_opinion",
                            WARN,
                            "POSSIBLE_WRONG_CLASS",
                            stem,
                            f"model nghi ngờ sai lớp: nhãn={best_diff_cls}, model={p_cls} (IoU={best_diff_iou:.2f})",
                            extra={
                                "conf": round(float(p_conf), 4),
                                "iou": round(float(best_diff_iou), 4),
                                "pred_cls": p_cls,
                                "label_cls": best_diff_cls,
                            },
                        )
                    )

        # 2. Kiểm tra POSSIBLE_FALSE_POS theo số dòng nhãn
        fp_preds = [
            (pcx, pcy, pw, ph)
            for _, p_conf, pcx, pcy, pw, ph in img_preds
            if p_conf >= fp_conf
        ]
        for line_no, g_cls, g_box in valid_gt:
            max_iou = max((iou_xywh(g_box, p_box) for p_box in fp_preds), default=0.0)
            if max_iou < iou_missing:
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_FALSE_POS",
                        stem,
                        f"box nhãn lớp {g_cls} không khớp dự đoán nào của model (max IoU={max_iou:.2f})",
                        line=line_no,
                        extra={"iou": round(float(max_iou), 4)},
                    )
                )

    return issues
