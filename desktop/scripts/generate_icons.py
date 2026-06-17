from PIL import Image, ImageDraw


def generate_icons(base_dir: str = "assets") -> None:
    sizes = {
        f"{base_dir}/icon.png": 512,
        f"{base_dir}/icon-256.png": 256,
        f"{base_dir}/icon-128.png": 128,
        f"{base_dir}/icon-64.png": 64,
        f"{base_dir}/icon-48.png": 48,
        f"{base_dir}/icon-32.png": 32,
    }

    for path, size in sizes.items():
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        r = int(size * 0.18)
        margin = int(size * 0.08)
        draw.rounded_rectangle(
            [margin, margin, size - margin, size - margin],
            radius=r,
            fill=(67, 97, 238),
        )

        env_m = int(size * 0.25)
        env_w = size - 2 * env_m
        env_h = int(env_w * 0.7)
        env_y = (size - env_h) // 2
        lw = max(2, size // 40)
        draw.rectangle(
            [env_m, env_y, env_m + env_w, env_y + env_h],
            outline="white",
            width=lw,
        )

        cx = size // 2
        draw.line(
            [(env_m, env_y), (cx, env_y + env_h // 2), (env_m + env_w, env_y)],
            fill="white",
            width=lw,
        )

        dot_r = int(size * 0.06)
        dot_x = size - env_m
        dot_y = env_y - dot_r - int(size * 0.02)
        draw.ellipse(
            [dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r],
            fill=(247, 37, 133),
        )
        lw2 = max(1, size // 80)
        draw.line([(dot_x - dot_r // 2, dot_y), (dot_x + dot_r // 2, dot_y)], fill="white", width=lw2)
        draw.line([(dot_x, dot_y - dot_r // 2), (dot_x, dot_y + dot_r // 2)], fill="white", width=lw2)

        img.save(path)

    ico_img = Image.open(f"{base_dir}/icon.png")
    ico_img.save(f"{base_dir}/icon.ico", format="ICO", sizes=[(32, 32), (64, 64), (128, 128), (256, 256)])

    print(f"Icons generated in {base_dir}/")


if __name__ == "__main__":
    import os
    base = os.path.join(os.path.dirname(__file__), "..", "assets")
    generate_icons(base)
