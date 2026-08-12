from PIL import Image, ImageDraw

DARK_SLATE = "#475C6C"
WARM_GRAY = "#8A8583"


def make_icon(path):
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # two overlapping "report" cards -- echoes the app's own two-pane layout
    draw.rounded_rectangle([40, 30, 190, 180], radius=28, fill=WARM_GRAY)
    draw.rounded_rectangle([70, 76, 220, 226], radius=28, fill=DARK_SLATE)

    img.save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    make_icon("icon.ico")
    print("wrote icon.ico")
