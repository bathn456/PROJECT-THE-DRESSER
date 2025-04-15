import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os
import time
from typing import Dict, List, Any
import json
from PIL import Image
import requests
from io import BytesIO

# Set page configuration
st.set_page_config(
    page_title="Outfit Recommender",
    page_icon="👔",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    /* Product Grid Layout */
    .product-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 20px;
        padding: 20px 0;
    }
    .product-card {
        background: white;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        overflow: hidden;
        transition: all 0.3s ease;
        position: relative;
    }
    .product-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    }
    .product-card:active {
        transform: translateY(0);
    }
    .product-image {
        width: 100%;
        height: 300px;
        object-fit: cover;
        transition: transform 0.3s ease;
    }
    .product-card:hover .product-image {
        transform: scale(1.05);
    }
    .product-info {
        padding: 15px;
        background: white;
    }
    .product-title {
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 8px;
        color: #333;
    }
    .product-price {
        font-size: 14px;
        color: #4CAF50;
        font-weight: 500;
    }
    .product-link {
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    .product-card:hover .product-link {
        opacity: 1;
    }
    .outfit-section {
        background: white;
        border-radius: 15px;
        padding: 20px;
        margin: 20px 0;
    }
    .outfit-header {
        font-size: 20px;
        font-weight: 600;
        margin-bottom: 15px;
        padding-bottom: 10px;
        border-bottom: 2px solid #4CAF50;
    }
    /* Hide Streamlit elements */
    .stDeployButton, #MainMenu, footer {
        display: none;
    }
    .warning-message {
        background-color: #fff3cd;
        color: #856404;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
        font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)

def generate_outfit_prompt(user_input: str) -> str:
    """Generate a focused outfit recommendation prompt."""
    return f"""
    Based on: "{user_input}"
    Generate an outfit combination in the following JSON format:
    {{
        "categories": [
            {{
                "name": "Üst Giyim",
                "items": [
                    {{
                        "name": "Ürün adı",
                        "brand": "Marka",
                        "price": "Fiyat",
                        "image_url": "https://product-image-url.com/image.jpg",
                        "product_url": "https://www.hepsiburada.com/urun-adi-p-123456"
                    }}
                ]
            }},
            {{
                "name": "Alt Giyim",
                "items": []
            }},
            {{
                "name": "Ayakkabı",
                "items": []
            }},
            {{
                "name": "Aksesuar",
                "items": []
            }}
        ]
    }}

    Requirements:
    - Each category must have exactly 2 items
    - All text must be in Turkish
    - Prices must be realistic in TL
    - DO NOT use Trendyol for any products or images
    - Use only these e-commerce sites and their real product URLs:
      * Hepsiburada: https://www.hepsiburada.com/[urun-adi]-p-[urun-kodu]
      * N11: https://www.n11.com/urun/[urun-adi]-p-[urun-kodu]
      * GittiGidiyor: https://www.gittigidiyor.com/[urun-adi]-p-[urun-kodu]
      * Amazon TR: https://www.amazon.com.tr/dp/[urun-kodu]
    - For image URLs, use real product images from the same e-commerce site
    - Make sure all URLs are complete and valid
    - Focus only on suggesting specific products, no additional text or explanations
    - Each product must have a unique and valid URL that leads to a real product page
    - Do not use placeholder or example URLs
    """

def parse_response(response_text: str) -> Dict:
    """Parse the response text into a dictionary, handling potential errors."""
    try:
        # Try to parse as JSON
        return json.loads(response_text)
    except json.JSONDecodeError:
        try:
            # Try to extract JSON from the text if it's wrapped in other content
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(response_text[start:end])
        except:
            pass
    return {"categories": []}

def create_product_card(image_url: str, name: str, brand: str, price: str, product_url: str = None) -> str:
    """Create a product card HTML with clickable link."""
    try:
        # Create a unique ID for the card using a simple hash of the product details
        card_id = f"card_{abs(hash(f'{brand}{name}{price}'))}"
        
        # Clean and validate the product URL
        if product_url and product_url != "https://www.example.com/product-page":
            # Remove any whitespace and ensure URL is properly formatted
            product_url = product_url.strip()
            if not product_url.startswith(('http://', 'https://')):
                product_url = 'https://' + product_url
            
            # Validate URL format for each e-commerce site
            if not any(domain in product_url for domain in ['hepsiburada.com', 'n11.com', 'gittigidiyor.com', 'amazon.com.tr']):
                # If URL is not from a valid e-commerce site, create a search URL
                search_query = f"{brand} {name}".replace(' ', '+')
                product_url = f"https://www.hepsiburada.com/ara?q={search_query}"
        else:
            # If no valid product URL, create a search URL for the product
            search_query = f"{brand} {name}".replace(' ', '+')
            product_url = f"https://www.hepsiburada.com/ara?q={search_query}"
        
        # Clean and validate the image URL
        if image_url and image_url != "https://www.example.com/product-image.jpg":
            image_url = image_url.strip()
            if not image_url.startswith(('http://', 'https://')):
                image_url = 'https://' + image_url
        else:
            # Use a placeholder image if no valid image URL
            image_url = "https://via.placeholder.com/300x300?text=Görsel+Bulunamadı"
        
        return f"""
        <div class="product-card" id="{card_id}">
            <a href="{product_url}" target="_blank" style="text-decoration: none; color: inherit;">
                <img src="{image_url}" alt="{name}" class="product-image" onerror="this.src='https://via.placeholder.com/300x300?text=Görsel+Bulunamadı'">
                <div class="product-info">
                    <div class="product-title">{brand} - {name}</div>
                    <div class="product-price">{price} TL</div>
                    <div class="product-link" style="font-size: 12px; color: #4CAF50; margin-top: 5px;">
                        Ürüne git →
                    </div>
                </div>
            </a>
        </div>
        """
    except Exception as e:
        st.error(f"Ürün kartı oluşturulurken hata: {str(e)}")
        return ""

def create_outfit_section(category: str, items: List[Dict]) -> str:
    """Create an outfit category section."""
    try:
        items_html = "".join([
            create_product_card(
                image_url=item.get('image_url', ''),
                name=item.get('name', ''),
                brand=item.get('brand', ''),
                price=item.get('price', ''),
                product_url=item.get('product_url', '')
            ) 
            for item in items 
            if all(k in item for k in ['name', 'brand', 'price', 'image_url'])
        ])
        if not items_html:
            return ""
        return f"""
        <div class="outfit-section">
            <div class="outfit-header">{category}</div>
            <div class="product-grid">{items_html}</div>
        </div>
        """
    except Exception:
        return ""

# Load environment variables and configure API
load_dotenv()
GOOGLE_API_KEY = os.getenv("GENAI_API_KEY")

if not GOOGLE_API_KEY:
    st.error("API anahtarı bulunamadı. Lütfen .env dosyasını kontrol edin.")
    st.stop()

try:
    genai.configure(api_key=GOOGLE_API_KEY)
    st.success("API başarıyla yapılandırıldı!")
except Exception as e:
    st.error(f"API yapılandırması sırasında hata oluştu: {str(e)}")
    st.stop()

# Initialize model
@st.cache_resource
def get_model():
    try:
        return genai.GenerativeModel('gemini-2.0-flash')
    except Exception as e:
        st.error(f"Model başlatılırken hata oluştu: {str(e)}")
        st.stop()

try:
    model = get_model()
    st.success("Model başarıyla yüklendi!")
except Exception as e:
    st.error(f"Model yüklenirken hata oluştu: {str(e)}")
    st.stop()

# UI
st.title("👔 Kıyafet Kombinleyici")

# User input
prompt = st.text_input(
    "Nasıl bir kombin arıyorsunuz?", 
    placeholder="Örnek: İş görüşmesi için resmi bir kombin"
)

if prompt:
    with st.spinner("Kombin hazırlanıyor..."):
        try:
            # Generate outfit recommendation
            response = model.generate_content(generate_outfit_prompt(prompt))
            
            # Parse the response
            outfit_data = parse_response(response.text)
            
            # Track if we've displayed any categories
            displayed_categories = 0
            
            # Display each category
            for category in outfit_data.get("categories", []):
                if category.get("name") and category.get("items"):
                    section_html = create_outfit_section(
                        category["name"],
                        category["items"]
                    )
                    if section_html:
                        st.markdown(section_html, unsafe_allow_html=True)
                        displayed_categories += 1
            
            # Show warning if no categories were displayed
            if displayed_categories == 0:
                st.markdown(
                    '<div class="warning-message">⚠️ Bazı ürünler gösterilemedi. Lütfen tekrar deneyin.</div>',
                    unsafe_allow_html=True
                )
                
        except Exception as e:
            st.markdown(
                f'<div class="warning-message">⚠️ Bir hata oluştu: {str(e)}</div>',
                unsafe_allow_html=True
            )

# Minimal sidebar
with st.sidebar:
    st.markdown("### Kombin Önerileri İçin İpuçları")
    st.markdown("""
    Daha iyi sonuçlar için şunları belirtin:
    - Ortam/Durum (iş, parti, günlük vb.)
    - Mevsim/Hava durumu
    - Tarz tercihiniz
    """)