"""Copy this file to Forge Neo's scripts/ directory and restart Neo.

Official Qwen Image 2.1 Turbo schedule; not Neo's unrelated "Turbo" scheduler.
Only the eight-step distilled checkpoint uses this schedule.
"""

import torch
from modules import sd_schedulers

SIGMAS = (1.0, 0.978453, 0.95418, 0.926626, 0.89508, 0.845148, 0.704534, 0.414568, 0.0)


def qwen21_turbo(n, sigma_min, sigma_max, device):
    if n != 8:
        raise ValueError("Qwen Image 2.1 Turbo requires 8 steps")
    return torch.tensor(SIGMAS, dtype=torch.float32, device=device)


if "qwen21_turbo" not in sd_schedulers.schedulers_map:
    scheduler = sd_schedulers.Scheduler("qwen21_turbo", "Qwen Image 2.1 Turbo", qwen21_turbo)
    sd_schedulers.all_schedulers.append(scheduler)
    sd_schedulers.schedulers.append(scheduler)
    sd_schedulers.schedulers_map[scheduler.name] = scheduler
    sd_schedulers.schedulers_map[scheduler.label] = scheduler
