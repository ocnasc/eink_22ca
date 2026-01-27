from PIL import Image, ImageDraw, ImageFont, ImageFilter
from datetime import datetime

def resize_cover(img, target_width, target_height):
    img_ratio = img.width / img.height
    target_ratio = target_width / target_height

    if img_ratio > target_ratio:
        # imagem é mais larga → corta lados
        new_height = target_height
        new_width = int(new_height * img_ratio)
    else:
        # imagem é mais alta → corta topo/baixo
        new_width = target_width
        new_height = int(new_width / img_ratio)

    img = img.resize((new_width, new_height), Image.LANCZOS)

    left = (new_width - target_width) // 2
    top = (new_height - target_height) // 2
    right = left + target_width
    bottom = top + target_height

    return img.crop((left, top, right, bottom))


def picture_frame(
    foto_path,
    frase_superior, # max 18 caracteres
    frase_inferior, # max 25 caracteres
    data_inicio="2024-09-21",
    output_path="resultado.png",
    dark_mode=False
):

    img = Image.open(foto_path).convert("RGBA")
    img = resize_cover(img, 800, 480)
    width, height = img.size


    # ===== CORES =====

    white_glass = (255, 255, 255, 150)
    grey_glass = (48, 48, 48, 150)

    white_elements = (255, 255, 255, 255)
    grey_elements = (48, 48, 48, 255)

    vidro = white_glass if not dark_mode else grey_glass
    line_color = grey_elements if not dark_mode else white_elements
    text_color = grey_elements if not dark_mode else white_elements


    # ===== CALCULAR DIAS =====
    data_inicial = datetime.strptime(data_inicio, "%Y-%m-%d")
    dias = (datetime.now() - data_inicial).days

    # ===== OVERLAY =====
    overlay_height = int(height * 0.23)
    overlay_top = height - overlay_height

    # ===== BLUR DO FUNDO (VIDRO REAL) =====
    regiao = img.crop((0, overlay_top, width, height))
    regiao_blur = regiao.filter(ImageFilter.GaussianBlur(radius=3))
    img.paste(regiao_blur, (0, overlay_top))

    # ===== OVERLAY TRANSLÚCIDO =====
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    draw.rectangle(
        [(0, overlay_top), (width, height)],
        fill=vidro
    )

    # ===== LINHAS =====

    line_width = 3
    center_x = width // 2

    # superior
    draw.rectangle(
        [(0, overlay_top), (width, overlay_top + line_width - 1)],
        fill=line_color
    )
    # inferior
    draw.rectangle(
        [(0, height - line_width), (width, height)],
        fill=line_color
    )
    # esquerda
    draw.rectangle(
        [(0, overlay_top), (line_width -1, height)],
        fill=line_color
    )
    # direita
    draw.rectangle(
        [(width - line_width, overlay_top), (width, height)],
        fill=line_color
    )
    # centro
    draw.rectangle(
        [(center_x - line_width // 2, overlay_top),
         (center_x + line_width // 2, height)],
        fill=line_color
    )

    # ===== FONTES =====
    try:
        fonte_msg_grande = ImageFont.truetype(
            "fonts/abril-fatface/abril-fatface-latin-400-normal.ttf",
            int(height * 0.075)
        )
        fonte_msg_pequena = ImageFont.truetype(
            "fonts/Italianno/Italianno-Regular.ttf",
            # "abril-fatface/abril-fatface-latin-400-normal.ttf",
            int(height * 0.09)
            # int(height * 0.048)
        )
        fonte_dias = ImageFont.truetype(
            # "abril-fatface/abril-fatface-latin-400-normal.ttf",
            "fonts/Italianno/Italianno-Regular.ttf",
            int(height * 0.12)
        )
        fonte_numero = ImageFont.truetype(
            "fonts/abril-fatface/abril-fatface-latin-400-normal.ttf",
            int(height * 0.12)
        )
    except:
        fonte_msg_grande = fonte_msg_pequena = fonte_dias = fonte_numero = ImageFont.load_default()


    draw_text = ImageDraw.Draw(overlay)

    # ===== LADO ESQUERDO =====
    bbox = draw_text.textbbox((0, 0), frase_superior, font=fonte_msg_grande)
    x = (center_x - (bbox[2] - bbox[0])) // 2
    y = overlay_top + int(overlay_height * 0.1)
    draw_text.text((x, y), frase_superior, fill=text_color, font=fonte_msg_grande)

    bbox = draw_text.textbbox((0, 0), frase_inferior, font=fonte_msg_pequena)
    x = (center_x - (bbox[2] - bbox[0])) // 2
    y = overlay_top + int(overlay_height * 0.495)
    draw_text.text((x, y), frase_inferior, fill=text_color, font=fonte_msg_pequena)

    # ===== LADO DIREITO =====
    numero = str(dias)
    bbox = draw_text.textbbox((0, 0), numero, font=fonte_numero)
    x = center_x + (center_x - (bbox[2] - bbox[0])) // 2
    y = overlay_top + int(overlay_height * 0.01) - 4

    draw_text.text((x, y), numero, fill=text_color, font=fonte_numero)

    texto = " dias ao seu lado    "
    bbox = draw_text.textbbox((0, 0), texto, font=fonte_dias)
    x = center_x + (center_x - (bbox[2] - bbox[0])) // 2
    y = overlay_top + int(overlay_height * 0.46) - 5
    draw_text.text((x, y), texto, fill=text_color, font=fonte_dias)
    # bbox = draw_text.textbbox((0, 0), texto, font=fonte_dias)
    # x = center_x + (center_x - (bbox[2] - bbox[0])) // 2
    # y = overlay_top + int(overlay_height * 0.56)
    # draw_text.text((x, y), texto, fill=text_color, font=fonte_dias)

    # ===== CORAÇÃO =====

    size = 45
    offset_x = -10
    offset_y = 10


    heart = Image.open("./assets/heart.png").convert("RGBA")

    heart_height = int(height * (size / 1000))
    heart_ratio = heart.width / heart.height
    heart_width = int(heart_height * heart_ratio)
    heart = heart.resize((heart_width, heart_height), Image.LANCZOS)

    margin = 60
    heart_x = width - heart_width - margin + offset_x
    heart_y = height - overlay_height + margin + offset_y

    overlay.paste(heart, (heart_x, heart_y), heart)


    # ===== COMPOSIÇÃO FINAL =====
    final = Image.alpha_composite(img, overlay)
    final.convert("RGB").save(output_path, "PNG")

    print(f"[OK] Imagem criada: {output_path}")
    print(f"[OK] Dias juntos: {dias}")


# EXEMPLO DE USO:
if __name__ == "__main__":
    # Configurações
    foto = "20251221_051855.jpg"  # Substitua pelo caminho da sua foto
    frase_top = "Bom dia, meu amor!"
    frase_bottom = "Te amo, minha linda"
    data_inicio = "2024-09-21"  # Data de início do relacionamento (YYYY-MM-DD)
    
    # Criar a imagem
    picture_frame(
        foto_path=foto,
        frase_superior=frase_top,
        frase_inferior=frase_bottom,
    )