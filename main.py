import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import os

def write_text_on_image(image_path, text, font_path, font_size, output_path, text_position, text_color):
    try:
        # Open the image
        img = Image.open(image_path).convert("RGBA")

        # Initialize ImageDraw
        draw = ImageDraw.Draw(img)

        # Load the font
        font = ImageFont.truetype(font_path, size=font_size)

        # Write text on the image
        draw.text(text_position, text, font=font, fill=text_color)

        # Save the result with explicit format specification
        img.save(output_path, format="PNG")

        st.image(img, caption='Result Image', use_column_width=True)

    except Exception as e:
        st.error(f"Error: {e}")

# Streamlit app
st.title("Text on Image App")

# Upload Image
image = st.file_uploader("Upload Image", type=["jpg", "jpeg", "png"])

# Text input
text_input = st.text_input("Enter Text")

# Font Size slider
font_size = st.slider("Select Font Size", min_value=10, max_value=100, value=30)

# Upload Font
font_file = st.file_uploader("Upload Font", type=["ttf"])

# Text Position input
text_position_x = st.number_input("Enter X-coordinate for Text", value=50)
text_position_y = st.number_input("Enter Y-coordinate for Text", value=50)
text_position = (text_position_x, text_position_y)

# Text Color input
text_color = st.color_picker("Choose Text Color", "#FFFFFF")

if image and text_input and font_file:
    st.success("Files uploaded successfully!")

    # Display user inputs
    output_folder = st.text_input("Enter Output Folder Path:", "Documents")
    output_filename = st.text_input("Enter Output Filename:", "output_image.png")

    # Combine folder and filename to create the complete output path
    output_path = os.path.join(output_folder, output_filename)

    os.makedirs(output_folder, exist_ok=True)

    if not output_folder:
        st.warning("Please enter a valid output folder path.")
    else:
        # Create output folder if it doesn't exist
        os.makedirs(output_folder, exist_ok=True)

        # Save the uploaded font file locally with the correct extension
        font_path_local = os.path.join(output_folder, "user_font.ttf")
        font_file_bytes = font_file.read()
        with open(font_path_local, "wb") as f:
            f.write(font_file_bytes)

        # Call the function to write text on the image
        write_text_on_image(image, text_input, font_path_local, font_size, output_path, text_position, text_color)

        st.success("Image generated successfully!")
