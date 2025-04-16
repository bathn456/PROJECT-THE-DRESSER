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

# sayfamızın genel görünümünü ayarlayalım
st.set_page_config(
    page_title="Kişisel Stilistiniz",
    page_icon="👔",
    layout="wide",
    initial_sidebar_state="expanded"
)

# sayfamızı güzelleştirecek CSS stilleri
st.markdown("""
<style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    /* ürünleri güzel bir ızgara düzeninde gösterelim */
    .product-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 20px;
        padding: 20px 0;
    }
    /* her bir ürün kartı için hoş bir tasarım */
    .product-card {
        background: white;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        overflow: hidden;
        transition: all 0.3s ease;
        position: relative;
    }
    /* kartların üzerine gelince hafifçe yükselme efekti */
    .product-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    }
    .product-card:active {
        transform: translateY(0);
    }
    /* ürün görselleri için stil ayarları */
    .product-image {
        width: 100%;
        height: 300px;
        object-fit: cover;
        transition: transform 0.3s ease;
    }
    /* görsele yakınlaşma efekti */
    .product-card:hover .product-image {
        transform: scale(1.05);
    }
    /* ürün bilgilerinin gösterileceği alan */
    .product-info {
        padding: 15px;
        background: white;
    }
    /* ürün başlığı stili */
    .product-title {
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 8px;
        color: #333;
    }
    /* fiyat gösterimi için özel stil */
    .product-price {
        font-size: 14px;
        color: #4CAF50;
        font-weight: 500;
    }
    /* "ürüne git" bağlantısı için hover efekti */
    .product-link {
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    .product-card:hover .product-link {
        opacity: 1;
    }
    /* her bir kombin kategorisi için özel bölüm */
    .outfit-section {
        background: white;
        border-radius: 15px;
        padding: 20px;
        margin: 20px 0;
    }
    /* kategori başlıkları için stil */
    .outfit-header {
        font-size: 20px;
        font-weight: 600;
        margin-bottom: 15px;
        padding-bottom: 10px;
        border-bottom: 2px solid #4CAF50;
    }
    /* streamlit'in bazı varsayılan öğelerini gizleyelim */
    .stDeployButton, #MainMenu, footer {
        display: none;
    }
    /* uyarı mesajları için özel stil */
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
    """Kullanıcının isteğini AI'ya anlatacak özel bir prompt hazırlayalım."""
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
    """AI'dan gelen yanıtı kullanılabilir bir formata çevirelim."""
    try:
        # Önce düz JSON olarak okumayı deneyelim
        return json.loads(response_text)
    except json.JSONDecodeError:
        try:
            # Eğer olmadıysa, metinin içinden JSON'ı bulup çıkaralım
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(response_text[start:end])
        except:
            pass
    return {"categories": []}

def create_product_card(image_url: str, name: str, brand: str, price: str, product_url: str = None) -> str:
    """Her bir ürün için güzel bir kart tasarlayalım."""
    try:
        # Her kart için benzersiz bir ID oluşturalım
        card_id = f"card_{abs(hash(f'{brand}{name}{price}'))}"
        
        # Ürün linkini temizleyip düzenleyelim
        if product_url and product_url != "https://www.example.com/product-page":
            product_url = product_url.strip()
            if not product_url.startswith(('http://', 'https://')):
                product_url = 'https://' + product_url
            
            # Sadece güvenilir e-ticaret sitelerinden ürün gösterelim
            if not any(domain in product_url for domain in ['hepsiburada.com', 'n11.com', 'gittigidiyor.com', 'amazon.com.tr']):
                search_query = f"{brand} {name}".replace(' ', '+')
                product_url = f"https://www.hepsiburada.com/ara?q={search_query}"
        else:
            # Eğer ürün linki yoksa, arama sonuçlarına yönlendirelim
            search_query = f"{brand} {name}".replace(' ', '+')
            product_url = f"https://www.hepsiburada.com/ara?q={search_query}"
        
        # Ürün görselini kontrol edelim
        if image_url and image_url != "https://www.example.com/product-image.jpg":
            image_url = image_url.strip()
            if not image_url.startswith(('http://', 'https://')):
                image_url = 'https://' + image_url
        else:
            # Görsel yoksa placeholder gösterelim
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
        st.error(f"Ürün kartı oluşturulurken bir sorun çıktı: {str(e)}")
        return ""

def create_outfit_section(category: str, items: List[Dict]) -> str:
    """Her kategori için özel bir bölüm hazırlayalım."""
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

# çevre değişkenlerini ve API'yi hazırlayalım
load_dotenv()
GOOGLE_API_KEY = os.getenv("GENAI_API_KEY")

if not GOOGLE_API_KEY:
    st.error("Hay aksi! API anahtarını bulamadım. .env dosyasını kontrol eder misin?")
    st.stop()

try:
    genai.configure(api_key=GOOGLE_API_KEY)
    st.success("Harika! API'ye başarıyla bağlandık! 🎉")
except Exception as e:
    st.error(f"API'ye bağlanırken bir sorun çıktı: {str(e)}")
    st.stop()

# aI modelimizi hazırlayalım
@st.cache_resource
def get_model():
    try:
        return genai.GenerativeModel('gemini-2.0-flash')
    except Exception as e:
        st.error(f"AI modelini başlatırken bir sorun yaşadık: {str(e)}")
        st.stop()

try:
    model = get_model()
    st.success("AI modelimiz hazır, başlayabiliriz! 🚀")
except Exception as e:
    st.error(f"AI modelini yüklerken bir sorun çıktı: {str(e)}")
    st.stop()

def main():
    st.title("👔 Kişisel Stilistiniz")
    
    st.markdown("""
    ### Merhaba! Ben senin kişisel stil danışmanınım 👋
    
    Bugün nasıl görünmek istediğini söyle, sana harika bir kombin hazırlayayım! İster iş görüşmesi için profesyonel bir görünüm, 
    ister hafta sonu için rahat bir stil - hayalindeki görünüme birlikte ulaşalım.
    
    #### Nasıl yardımcı olabilirim?
    1. 💭 Aklındaki durumu veya tarzı bana anlat
    2. 🎨 Senin için özel kombinler hazırlayayım
    3. 🛍️ Beğendiğin parçaları hemen satın alabilirsin
    
    *İpucu: Ne kadar detaylı anlatırsan, o kadar isabetli öneriler sunabilirim!*
    """)
    
    user_input = st.text_area(
        "Hadi başlayalım! Nasıl bir kombin arıyorsun?",
        placeholder="Örneğin: 'Yarın önemli bir iş görüşmem var, profesyonel ama şık görünmek istiyorum' ya da 'Hafta sonu arkadaşlarla brunch'a gideceğim, rahat ama cool bir şeyler arıyorum'",
        help="İstediğin tarzı, gideceğin yeri veya nasıl hissetmek istediğini anlatabilirsin. Renk tercihlerin varsa onları da ekleyebilirsin!"
    )
    
    if st.button("✨ Kombinimi Oluştur", type="primary"):
        if not user_input:
            st.warning("Ups! Önce nasıl bir kombin istediğini anlatır mısın?")
            return
        
        try:
            with st.spinner("Senin için harika bir kombin hazırlıyorum... 🎨"):
                model = get_model()
                prompt = generate_outfit_prompt(user_input)
                response = model.generate_content(prompt)
                outfit_data = parse_response(response.text)
                
                if outfit_data and "categories" in outfit_data:
                    st.success("İşte senin için seçtiğim parçalar! 🌟")
                    for category in outfit_data["categories"]:
                        if "name" in category and "items" in category:
                            outfit_section = create_outfit_section(category["name"], category["items"])
                            if outfit_section:
                                st.markdown(outfit_section, unsafe_allow_html=True)
                else:
                    st.error("Ah, bir sorun oluştu! Başka bir kombin denemek ister misin?")
                
        except Exception as e:
            st.error(f"Bir hata oluştu: {str(e)}")
            st.warning("Üzgünüm, tekrar deneyebilir miyiz? Belki biraz daha farklı bir şekilde anlatabilirsin.")

if __name__ == "__main__":
    main()

# yardımcı ipuçları için kenar çubuğu
with st.sidebar:
    st.markdown("### 💡 Daha İyi Kombinler İçin İpuçları") 