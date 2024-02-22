import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import os
import requests
import textwrap
from zipfile import ZipFile
from io import BytesIO
import base64

def find_empty_space(template_image):
    # Function to find the coordinates of the empty space in the template image
    template_image = template_image.convert("RGBA")
    alpha_data = template_image.getchannel("A")

    non_empty_rows = any(alpha_data.getpixel((x, y)) != 0 for y in range(template_image.size[1]) for x in range(template_image.size[0]))
    non_empty_cols = any(alpha_data.getpixel((x, y)) != 0 for x in range(template_image.size[0]) for y in range(template_image.size[1]))

    top = 0
    bottom = template_image.size[1]
    left = 0
    right = template_image.size[0]

    if non_empty_rows:
        for y in range(template_image.size[1]):
            if all(alpha_data.getpixel((x, y)) == 0 for x in range(template_image.size[0])):
                top = y
                break

        for y in range(template_image.size[1] - 1, -1, -1):
            if all(alpha_data.getpixel((x, y)) == 0 for x in range(template_image.size[0])):
                bottom = y
                break

    if non_empty_cols:
        for x in range(template_image.size[0]):
            if all(alpha_data.getpixel((x, y)) == 0 for y in range(template_image.size[1])):
                left = x
                break

        for x in range(template_image.size[0] - 1, -1, -1):
            if all(alpha_data.getpixel((x, y)) == 0 for y in range(template_image.size[1])):
                right = x
                break

    return top, bottom, left, right

def save_uploaded_font(font_file, prefix, index):
    # Create "fonts" folder if it doesn't exist
    os.makedirs("fonts", exist_ok=True)
    # Save the uploaded font file locally with the correct extension
    font_path_local = os.path.join("fonts", f"{prefix}_font_{index}.ttf")
    font_file_bytes = font_file.read()
    with open(font_path_local, "wb") as f:
        f.write(font_file_bytes)
    return font_path_local

def write_text_on_image(img, text_data):
    draw = ImageDraw.Draw(img)
    for text, font_path, font_size, position, text_color in text_data:
        font = ImageFont.truetype(font_path, size=font_size)

        para = textwrap.wrap(text, width=22)
        total_height = sum(draw.textsize(line, font=font)[1] for line in para)
        y_position = position[1] - total_height // 2

        for line in para:
            w, h = draw.textsize(line, font=font)
            x_position = position[0] - w // 2
            draw.text((x_position, y_position), line, font=font, fill=text_color)
            y_position += h

def resize_image(image, target_size, empty_space_position):
    width, height = image.size
    target_width, target_height = target_size

    aspect_ratio = width / height
    target_aspect_ratio = target_width / target_height

    if aspect_ratio > target_aspect_ratio:
        new_width = target_width
        new_height = int(target_width / aspect_ratio)
    else:
        new_height = target_height
        new_width = int(target_height * aspect_ratio)

    white_img = Image.new("RGBA", target_size, (0, 0, 0, 0))
    resized_image = image.resize((new_width, new_height), Image.LANCZOS)

    left = (new_width - target_width) / 2
    top = (new_height - target_height) / 2
    right = (new_width + target_width) / 2
    bottom = (new_height + target_height) / 2

    if empty_space_position == "top":
        top = 0
        bottom = target_height
    elif empty_space_position == "bottom":
        top = target_height - new_height
        bottom = target_height

    resized_image = resized_image.crop((left, top, right, bottom))
    white_img.paste(resized_image, (0, 0))

    return white_img

def download_image(url, output_path, filename):
    response = requests.get(url, stream=True)
    image_path = os.path.join(output_path, f"{filename}.png")

    if response.status_code == 200:
        with open(image_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

    return image_path

def get_download_link(zip_buffer):
    # Function to get a download link for the in-memory zip file
    zip_filename = "generated_images.zip"
    zip_data = zip_buffer.getvalue()
    b64_zip_data = base64.b64encode(zip_data).decode()
    href = f'<a href="data:application/zip;base64,{b64_zip_data}" download="{zip_filename}">Click here to download ZIP file</a>'

    return href


def generate_images(excel_file, template_images, text_data_by_template):
    data = pd.read_excel(excel_file)

    zip_buffer = BytesIO()  # Create an in-memory zip file

    with ZipFile(zip_buffer, 'a') as zipf:
        for i, template_image_path in enumerate(template_images):
            template_image = Image.open(template_image_path).convert("RGBA")
            st.write(f"### Template {i + 1} ({template_image.size[0]}x{template_image.size[1]})")

            text_data_by_column = text_data_by_template.get(f"Template {i + 1}", {})
            template_width, template_height = template_image.size

            dimensions_to_column = {
                (1080, 1080): 'photo_url_square',
                (1080, 1920): 'photo_url_story',
                (1200, 628): 'photo_url_landscape',
                (1920, 1080): 'photo_url_wide',
            }

            photo_url_column = dimensions_to_column.get((template_width, template_height), None)

            if photo_url_column is None:
                st.error(f"No matching photo_url column for template {i + 1} dimensions: {template_width}x{template_height}")
                continue

            top, bottom, left, right = find_empty_space(template_image)

            for index, row in data.iterrows():
                img_url = row[photo_url_column]
                img_path = download_image(img_url, ".", f"{row['shop_id']}_image")
                url_img = Image.open(img_path).convert("RGBA")

                empty_space_position = "top" if top < template_image.height / 2 else "bottom"
                url_img = resize_image(url_img, template_image.size, empty_space_position)

                result_img = Image.new("RGBA", template_image.size, (0, 0, 0, 0))
                result_img.paste(template_image, (0, 0))

                if top < template_image.height / 2:
                    result_img = Image.alpha_composite(url_img, template_image)
                else:
                    result_img = Image.alpha_composite(url_img, template_image)

                for column, text_data in text_data_by_column.items():
                    text, font_path, font_size, position, text_color = text_data
                    cell_content = str(row[column])
                    final_text = cell_content if cell_content else text

                    if final_text:
                        text_data_for_column = [(final_text, font_path, font_size, position, text_color)]
                        write_text_on_image(result_img, text_data_for_column)

                # Save the image to the in-memory zip file
                img_filename = f"{row['shop_id']}_result_{i + 1}_{template_width}x{template_height}.png"

                # Save the image to a BytesIO buffer
                image_buffer = BytesIO()
                result_img.save(image_buffer, format="PNG")
                image_data = image_buffer.getvalue()

                # Write the BytesIO buffer to the ZIP file
                zipf.writestr(img_filename, image_data)


            for index, row in data.iterrows():
                img_path = os.path.join(".", f"{row['shop_id']}_image.png")
                os.remove(img_path)

    return zip_buffer

# Streamlit App
st.title("Image Generator App")

input_type = st.radio("Choose Input Type:", ["Excel File", "Single Image"])

if input_type == "Excel File":
    excel_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])

    if excel_file:
        st.success("Excel file uploaded successfully!")
        columns = pd.read_excel(excel_file).columns.tolist()

        selected_columns = st.multiselect("Select Columns to Include in Image", columns)
        template_images = st.file_uploader("Upload Template Images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

        if template_images:
            st.success("Template images uploaded successfully!")

            text_data_by_template = {}
            for i, template_image in enumerate(template_images):
                image_dimensions = Image.open(template_image).size
                st.write(f"### Template {i + 1} ({image_dimensions[0]}x{image_dimensions[1]})")
                text_data_by_column = {}
                for col in selected_columns:
                    st.write(f"#### Column: {col}")
                    font_path_local = st.file_uploader(f"Upload Font for {col} - Template {i + 1}", type=["ttf"])
                    font_size = st.slider(f"Select Font Size for {col} - Template {i + 1}", min_value=10, max_value=140, value=30)
                    position_x = st.number_input(f"Enter X-coordinate for {col} - Template {i + 1}", value=50)
                    position_y = st.number_input(f"Enter Y-coordinate for {col} - Template {i + 1}", value=50)
                    text_color = st.color_picker(f"Choose Text Color for {col} - Template {i + 1}", "#FFFFFF")

                    text = col

                    if text and font_path_local:
                        font_path_local = save_uploaded_font(font_path_local, col, i + 1)
                        text_data_by_column[col] = (text, font_path_local, font_size, (position_x, position_y), text_color)

                text_data_by_template[f"Template {i + 1}"] = text_data_by_column

            if st.button("Generate Images"):
                zip_buffer = generate_images(excel_file, template_images, text_data_by_template)
                st.success("Images generated successfully!")

                # Provide a direct link to download the zip file
                st.markdown(get_download_link(zip_buffer), unsafe_allow_html=True)

elif input_type == "Single Image":
    template_images = st.file_uploader("Upload Template Images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

    if template_images:
        st.success("Template images uploaded successfully!")
        font_size = st.slider("Select Font Size", min_value=10, max_value=100, value=30, key="font_size")
        num_texts = st.selectbox("Select Number of Texts", list(range(1, 6)), index=0, key="num_texts")
        texts = []
        text_positions = []

        for i in range(num_texts):
            texts.append(st.text_input(f"Enter Text {i + 1}"))
            text_positions_x = st.number_input(f"Enter X-coordinate for Text {i + 1}", value=50)
            text_positions_y = st.number_input(f"Enter Y-coordinate for Text {i + 1}", value=50)
            text_positions.append((text_positions_x, text_positions_y))

        font_size = st.slider("Select Font Size", min_value=10, max_value=100, value=30)
        font_file = st.file_uploader("Upload Font", type=["ttf"])
        text_color = st.color_picker("Choose Text Color", "#FFFFFF")

        if template_images and texts and font_file:
            st.success("Files uploaded successfully!")
            text_data_for_image = [(text, font_file, font_size, position, text_color) for text, position in zip(texts, text_positions)]
            text_data_by_template = {"Template 1": {"Single Image": text_data_for_image}}

            if st.button("Generate Images"):
                zip_buffer = generate_images(None, template_images, text_data_by_template)
                st.success("Image generated successfully!")

                # Provide a direct link to download the zip file
                st.markdown(get_download_link(zip_buffer), unsafe_allow_html=True)
