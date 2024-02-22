import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import os
import requests
import textwrap
import base64

# Function to generate images
def generate_images(excel_file, template_images, text_data_by_column, output_path, coordinates):
    data = pd.read_excel(excel_file)

    for i, template_image in enumerate(template_images, start=1):
        # Check if the template_image is provided and is an image file
        if template_image is not None:
            try:
                template_image = Image.open(template_image).convert("RGBA")
            except Exception as e:
                st.error(f"Error opening template image {i}: {e}")
                continue
        else:
            st.error(f"Invalid or missing template image file {i}.")
            continue

        # Get the dimensions of the template image
        template_width, template_height = template_image.size

        # Map dimensions to corresponding photo_url column
        dimensions_to_column = {
            (1080, 1080): 'photo_url_square',
            (1080, 1920): 'photo_url_story',
            (1200, 628): 'photo_url_landscape',
            (1920, 1080): 'photo_url_wide',
            # Add more dimensions as needed
        }

        # Get the corresponding photo_url column based on dimensions
        photo_url_column = dimensions_to_column.get((template_width, template_height), None)

        if photo_url_column is None:
            st.error(f"No matching photo_url column for template {i} dimensions: {template_width}x{template_height}")
            continue

        for index, row in data.iterrows():
            # Download and open image from URL based on the selected column
            img_url = row[photo_url_column]
            img_path = download_image(img_url, output_path, f"{row['shop_id']}_image")
            url_img = Image.open(img_path).convert("RGBA")

            # Resize URL image to match the dimensions of the template image
            url_img = resize_image(url_img, template_image.size)

            # Composite the images
            result_img = Image.alpha_composite(url_img, template_image)

            # Write text on the composed image for each selected column
            for column, text_data in text_data_by_column.items():
                text, font_path, font_size, text_color = text_data
                cell_content = str(row[column])
                final_text = cell_content if cell_content else text

                if final_text:
                    # Get the coordinates for the text
                    position_x, position_y = coordinates.get((i, column), (0, 0))

                    text_data_for_column = [(final_text, font_path, font_size, (position_x, position_y), text_color)]
                    write_text_on_image(result_img, text_data_for_column)

            # Save the resulting image
            result_img.save(os.path.join(output_path, f"{row['shop_id']}_result_{i}_{template_width}x{template_height}.png"))

            # Save the resized image locally
            resized_image_path = os.path.join(output_path, f"{row['shop_id']}_resized_{i}_{template_width}x{template_height}.png")
            url_img.save(resized_image_path)

# Function to write text on the image
def write_text_on_image(img, text_data):
    draw = ImageDraw.Draw(img)
    for text, font_path, font_size, position, text_color in text_data:
        font = ImageFont.truetype(font_path, size=font_size)

        para = textwrap.wrap(text, width=30)
        total_height = sum(draw.textsize(line, font=font)[1] for line in para)
        y_position = position[1] - total_height // 2

        for line in para:
            w, h = draw.textsize(line, font=font)
            x_position = position[0] - w // 2
            draw.text((x_position, y_position), line, font=font, fill=text_color)
            y_position += h

# Function to resize an image while maintaining the aspect ratio and matching target dimensions
def resize_image(image, target_size):
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

    resized_image = image.resize((new_width, new_height), Image.LANCZOS)

    left = (new_width - target_width) / 2
    top = (new_height - target_height) / 2
    right = (new_width + target_width) / 2
    bottom = (new_height + target_height) / 2

    resized_image = resized_image.crop((left, top, right, bottom))

    return resized_image

# Function to download an image from a URL and save it locally
def download_image(url, output_path, filename):
    response = requests.get(url, stream=True)
    image_path = os.path.join(output_path, f"{filename}.png")

    if response.status_code == 200:
        with open(image_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

    return image_path

# Function to save an uploaded font file locally
def save_uploaded_font(font_upload, column, template_num):
    # Generate a unique name for the font file
    font_filename = f"font_{column}_{template_num}.ttf"
    font_path_local = os.path.join("fonts", font_filename)

    # Save the font file locally
    with open(font_path_local, "wb") as f:
        f.write(font_upload.read())

    return font_path_local

# Streamlit app
st.title("Image Generator App")

# Choose input type: Excel or Single Image
input_type = st.radio("Choose Input Type:", ["Excel File"])

if input_type == "Excel File":
    # Upload Excel file
    excel_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])

    # Display user inputs
    if excel_file:
        st.success("Excel file uploaded successfully!")

        # Get the columns from the Excel file
        columns = pd.read_excel(excel_file).columns.tolist()

        # Multi-select dropdown for selecting columns
        selected_columns = st.multiselect("Select Columns to Include in Image", columns)

        # Upload multiple template images
        template_images = st.file_uploader("Upload Template Images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

        if template_images:
            st.success("Template images uploaded successfully!")

            # Display user inputs
            output_path = st.text_input("Enter Output Folder Path:", "output_images")

            # Get the number of template images
            num_templates = len(template_images)

            # Text and Font Size input for each template size and selected column
            text_data_by_column = {}
            coordinates = {}  # Dictionary to store coordinates for each column

            for i, template_image in enumerate(template_images, start=1):
                st.write(f"### Template {i}")

                for col in selected_columns:
                    st.write(f"#### Column: {col}")
                    text = st.text_input(f"Enter Text for {col} - Template {i}", col)
                    font_path_local = st.file_uploader(f"Upload Font for {col} - Template {i}", type=["ttf"])
                    font_size = st.slider(f"Select Font Size for {col} - Template {i}", min_value=10, max_value=100, value=30)

                    # Use coordinates based on user click on the image
                    if col not in coordinates.get(i, {}):
                        st.image(template_image, caption=f"Click on the image to set coordinates for {col}")
                        if st.button(f"Set Coordinates for {col} - Template {i}"):
                            x, y = st.pydeck_chart(lambda: st.pydeck_chart(
                                {
                                    "layers": [
                                        {
                                            "type": "ScatterplotLayer",
                                            "data": [{"position": [0, 0]}],
                                            "getColor": [255, 0, 0],
                                            "getRadius": 100,
                                        },
                                    ],
                                }
                            ))
                            if i not in coordinates:
                                coordinates[i] = {}
                            coordinates[i][col] = (x, y)

                    text_color = st.color_picker(f"Choose Text Color for {col} - Template {i}", "#FFFFFF")

                    if text and font_path_local:
                        # Create "fonts" folder if it doesn't exist
                        os.makedirs("fonts", exist_ok=True)
                        # Save the uploaded font file locally with the correct extension
                        font_path_local = save_uploaded_font(font_path_local, col, i)

                        text_data_by_column[col] = (text, font_path_local, font_size, text_color)

            # Generate images on button click
            if st.button("Generate Images", key=f"generate_button_{i}"):
                # Create output folder if it doesn't exist
                os.makedirs(output_path, exist_ok=True)

                # Call the function to generate images
                generate_images(excel_file, template_images, text_data_by_column, output_path, coordinates)

                st.success("Images generated successfully!")
