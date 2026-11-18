"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework."""
from ..common import ERROR, WARN


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    stems_set = set(image_stems)
    reviewed_set = set(reviewed)
    n_images = len(stems_set)

    errors = [iss for iss in issues if iss.severity == ERROR]
    n_errors = len(errors)

    warn_images = {
        iss.image
        for iss in issues
        if iss.severity == WARN and iss.image in stems_set and iss.image not in reviewed_set
    }
    n_warn_images = len(warn_images)
    warn_ratio = round(n_warn_images / n_images, 4) if n_images > 0 else 0.0
    hold_thr = cfg["gate"]["warn_ratio_hold"]

    reasons = []
    if n_errors >= 1:
        decision = "Rework"
        reasons.append(f"Còn {n_errors} lỗi bắt buộc (severity ERROR) chưa được xử lý.")
    elif warn_ratio >= hold_thr:
        decision = "Hold"
        reasons.append(
            f"Tỉ lệ ảnh còn cảnh báo chưa duyệt là {n_warn_images}/{n_images} = {warn_ratio:.2%} (>= ngưỡng {hold_thr:.0%})."
        )
    else:
        decision = "Release"
        reasons.append(
            f"Không còn lỗi bắt buộc; tỉ lệ ảnh cảnh báo chưa duyệt {n_warn_images}/{n_images} = {warn_ratio:.2%} (< {hold_thr:.0%})."
        )

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": warn_ratio,
        "reasons": reasons,
    }
