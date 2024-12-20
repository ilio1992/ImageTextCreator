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

    try:
        # Save the uploaded font file locally with the correct extension
        font_path_local = os.path.join("fonts", f"{prefix}_font_{index}.ttf")
        font_file_bytes = font_file.read()
        with open(font_path_local, "wb") as f:
            f.write(font_file_bytes)
        return font_path_local
    except Exception as e:
        print(f"Error saving font file: {e}")
        return None


def adjust_font_to_fit(text, font_path, max_width):
    font_size = 100
    font = ImageFont.truetype(font_path, font_size)
    text_bbox = font.getbbox(text)
    text_width = text_bbox[2] - text_bbox[0]

    while text_width > max_width:
        font_size -= 1
        font = ImageFont.truetype(font_path, font_size)
        text_bbox = font.getbbox(text)
        text_width = text_bbox[2] - text_bbox[0]

    return font_size


# Function to write text on an image with optional font adjustment, text wrapping, and vertical centering
def write_text_on_image(img, text_data, adjust_font=False, max_width=None):
    draw = ImageDraw.Draw(img)

    for text, font_path, font_size, position, text_color in text_data:
        try:
            if not os.path.exists(font_path):
                raise FileNotFoundError(f"Font file not found: {font_path}")

            if adjust_font and max_width:
                font_size = adjust_font_to_fit(text, font_path, max_width)

            font = ImageFont.truetype(font_path, size=font_size)
        except Exception as e:
            print(f"Error loading font '{font_path}': {e}. Using default font.")
            font = ImageFont.load_default()

        # Text wrapping
        para = textwrap.wrap(text, width=30)

        # Calculate total height for vertical centering
        total_height = sum(draw.textbbox((0, 0), line, font=font)[3] for line in para)
        y_position = position[1] - total_height // 2

        # Draw each line of wrapped text
        for line in para:
            bbox = draw.textbbox((0, 0), line, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x_position = position[0] - w // 2  # Horizontal centering
            draw.text((x_position, y_position), line, font=font, fill=text_color)
            y_position += h  # Move the y_position down after each line


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
    # Initialize an in-memory zip file to store the generated images
    zip_buffer = BytesIO()

    # Open the zip file in write mode
    with ZipFile(zip_buffer, 'a') as zipf:
        # Check if an Excel file is provided
        if excel_file:
            # Load the data from the Excel file
            data = pd.read_excel(excel_file)

            # Process each template image
            for i, template_image_path in enumerate(template_images):
                template_image = Image.open(template_image_path).convert("RGBA")
                st.write(f"### Processing Template {i + 1}")

                # Get text data associated with this template
                text_data_by_column = text_data_by_template.get(f"Template {i + 1}", {})

                # Determine the column to use for the image URL based on template dimensions
                template_width, template_height = template_image.size
                dimensions_to_column = {
                    (1080, 1080): 'photo_url_square',
                    (1080, 1920): 'photo_url_story',
                    (1200, 628): 'photo_url_landscape',
                    (1920, 1080): 'photo_url_wide',
                }
                photo_url_column = dimensions_to_column.get((template_width, template_height), None)

                if not photo_url_column:
                    st.error(f"No matching photo URL column for template dimensions {template_width}x{template_height}")
                    continue

                # Process each row in the Excel file
                for index, row in data.iterrows():
                    img_url = row[photo_url_column]
                    img_path = download_image(img_url, ".", f"{row['shop_id']}_image")
                    img_to_overlay = Image.open(img_path).convert("RGBA")

                    # Resize image and position it in the template
                    top, bottom, left, right = find_empty_space(template_image)
                    empty_space_position = "top" if top < template_image.height / 2 else "bottom"
                    img_to_overlay = resize_image(img_to_overlay, template_image.size, empty_space_position)

                    # Composite the overlay image with the template image
                    result_img = Image.alpha_composite(img_to_overlay, template_image)

                    # Add text onto the image
                    for column, text_data in text_data_by_column.items():
                        text, font_path, font_size, position, text_color = text_data
                        cell_content = str(row[column])
                        final_text = cell_content if cell_content else text
                        if final_text:
                            write_text_on_image(result_img, [(final_text, font_path, font_size, position, text_color)])

                    # Save the image into the zip file
                    img_filename = f"{row['shop_id']}_result_{i + 1}_{template_width}x{template_height}.png"
                    image_buffer = BytesIO()
                    result_img.save(image_buffer, format="PNG")
                    zipf.writestr(img_filename, image_buffer.getvalue())
                    os.remove(img_path)  # Remove the downloaded image after processing

        else:
            # If no Excel file is provided, process a single image without Excel data
            for i, template_image_path in enumerate(template_images):
                template_image = Image.open(template_image_path).convert("RGBA")
                text_data_by_column = text_data_by_template.get(f"Template {i + 1}", {})

                # Add provided text directly to the template image
                for col, text_data_for_column in text_data_by_column.items():
                    write_text_on_image(template_image, text_data_for_column)

                # Save the image to the zip file
                img_filename = f"result_{i + 1}_{template_image.size[0]}x{template_image.size[1]}.png"
                image_buffer = BytesIO()
                template_image.save(image_buffer, format="PNG")
                zipf.writestr(img_filename, image_buffer.getvalue())

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

        font_file = st.file_uploader("Upload Font", type=["ttf"])
        text_color = st.color_picker("Choose Text Color", "#FFFFFF")

        if template_images and texts and font_file:
            st.success("Files uploaded successfully!")
            text_data_for_image = [(text, font_file, font_size, position, text_color) for text, position in zip(texts, text_positions)]
            text_data_by_template = {"Template 1": {"Single Image": text_data_for_image}}

            if st.button("Generate Images"):
                # Generate the single image
                template_image_path = template_images[0]  # Only process the first uploaded template image
                template_image = Image.open(template_image_path).convert("RGBA")
                write_text_on_image(template_image, text_data_for_image)

                # Display the generated image directly in Streamlit
                st.image(template_image, caption="Generated Image", use_column_width=True)

                # Provide a download button for the generated image
                buffer = BytesIO()
                template_image.save(buffer, format="PNG")
                buffer.seek(0)

                b64 = base64.b64encode(buffer.getvalue()).decode()
                href = f'<a href="data:image/png;base64,{b64}" download="generated_image.png">Click here to download the image</a>'
                st.markdown(href, unsafe_allow_html=True)
