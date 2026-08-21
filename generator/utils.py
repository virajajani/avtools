
# ============================================
# FILE 5: generator/utils.py
# ============================================

from PIL import Image, ImageDraw, ImageFont
import io
import base64
from decimal import Decimal
import random

# Meesho Accurate Shipping Rates (Based on 2025 data)
SHIPPING_RATES = {
    'local': [       # same city / within ~50km of pickup
        {'min': 0, 'max': 250, 'rate': 53},
        {'min': 251, 'max': 500, 'rate': 58},
        {'min': 501, 'max': 1000, 'rate': 64},
        {'min': 1001, 'max': 2000, 'rate': 75},
        {'min': 2001, 'max': 5000, 'rate': 84},
    ],
    'zonal': [       # same state / region
        {'min': 0, 'max': 250, 'rate': 53},
        {'min': 251, 'max': 500, 'rate': 58},
        {'min': 501, 'max': 1000, 'rate': 64},
        {'min': 1001, 'max': 2000, 'rate': 75},
        {'min': 2001, 'max': 5000, 'rate': 84},
    ],
    'national': [    # across India
        {'min': 0, 'max': 250, 'rate': 53},
        {'min': 251, 'max': 500, 'rate': 58},
        {'min': 501, 'max': 1000, 'rate': 64},
        {'min': 1001, 'max': 2000, 'rate': 75},
        {'min': 2001, 'max': 5000, 'rate': 84},
    ]
}

CATEGORIES = {
    'necklaces': {'name': 'Necklaces & Chains', 'weight': 250},
    'earrings': {'name': 'Earrings', 'weight': 50},
    'rings': {'name': 'Rings', 'weight': 30},
    'sarees': {'name': 'Sarees', 'weight': 600},
    'kurtis': {'name': 'Kurtis', 'weight': 300},
    'bangles': {'name': 'Bangles & Bracelets', 'weight': 150},
    'watches': {'name': 'Watches', 'weight': 100},
    'bags': {'name': 'Bags & Wallets', 'weight': 400},
}

BORDER_COLORS = [
    '#00FF00', '#FF1493', '#FF8C00', '#00BFFF', '#FFFF00', '#FF0000',
    '#9400D3', '#00CED1', '#FF69B4', '#32CD32', '#FFD700', '#FF6347',
]

STICKERS = [
    {'text': 'HOT', 'color': '#FFFFFF', 'bg': '#FF0000', 'size': 24},
    {'text': 'NEW', 'color': '#FFFFFF', 'bg': '#FF1493', 'size': 24},
    {'text': 'OFFER', 'color': '#FFFFFF', 'bg': '#FF8C00', 'size': 20},
    {'text': '✓', 'color': '#00FF00', 'bg': None, 'size': 50},
    {'text': '50% OFF', 'color': '#FFFFFF', 'bg': '#FF0000', 'size': 18},
    {'text': 'SALE', 'color': '#FFFFFF', 'bg': '#FF1493', 'size': 24},
    {'text': 'DEAL', 'color': '#FFFFFF', 'bg': '#00CED1', 'size': 24},
    {'text': '★', 'color': '#FFD700', 'bg': None, 'size': 50},
]


def get_shipping_rate(weight_grams, zone='zonal'):
    # \"\"\"Calculate shipping rate based on weight and zone\"\"\"
    rates = SHIPPING_RATES.get(zone, SHIPPING_RATES['zonal'])
    
    for rate_info in rates:
        if rate_info['min'] <= weight_grams <= rate_info['max']:
            return rate_info['rate']
    
    # For weights above max, use highest rate + additional charge
    return rates[-1]['rate'] + ((weight_grams - rates[-1]['max']) // 500) * 10


def calculate_pricing(cost_price, selling_price, shipping_rate, gst_rate=5):
    # \"\"\"
    # Calculate Meesho pricing breakdown
    # Meesho charges 0% commission + 18% GST on shipping
    # \"\"\"
    cost = Decimal(str(cost_price))
    selling = Decimal(str(selling_price))
    shipping = Decimal(str(shipping_rate))
    gst_percent = Decimal(str(gst_rate))
    
    # Calculate GST on shipping (18%)
    shipping_gst = shipping * Decimal('0.18')
    total_shipping_cost = shipping + shipping_gst
    
    # Calculate GST on product price
    product_gst = (selling * gst_percent) / (Decimal('100') + gst_percent)
    
    # Meesho Commission (0% for most categories)
    meesho_commission = Decimal('0')
    
    # Net earnings
    net_revenue = selling - total_shipping_cost - meesho_commission
    profit = net_revenue - cost
    
    # Customer pays
    customer_price = selling + shipping + shipping_gst
    
    return {
        'cost_price': float(cost),
        'selling_price': float(selling),
        'meesho_price': float(selling),
        'shipping_rate': float(shipping),
        'shipping_gst': float(shipping_gst),
        'total_shipping': float(total_shipping_cost),
        'product_gst': float(product_gst),
        'meesho_commission': float(meesho_commission),
        'net_revenue': float(net_revenue),
        'profit': float(profit),
        'customer_price': float(customer_price),
        'profit_margin': float((profit / selling) * 100) if selling > 0 else 0,
    }


def generate_image_variations(image_file, category='necklaces', num_images=56):
    # \"\"\"Generate multiple image variations with borders and stickers\"\"\"
    img = Image.open(image_file).convert('RGBA')
    
    # Resize to standard size
    target_size = (400, 400)
    img.thumbnail(target_size, Image.Resampling.LANCZOS)
    
    # Create white background and paste centered
    base_img = Image.new('RGBA', target_size, 'white')
    offset = ((target_size[0] - img.size[0]) // 2, (target_size[1] - img.size[1]) // 2)
    base_img.paste(img, offset, img if img.mode == 'RGBA' else None)
    
    variations = []
    weight = CATEGORIES.get(category, CATEGORIES['necklaces'])['weight']
    
    zones = ['local', 'zonal', 'national']
    
    for i in range(num_images):
        # Create new image with border
        border_width = 15
        bordered_size = (target_size[0] + border_width * 2, target_size[1] + border_width * 2)
        border_color = BORDER_COLORS[i % len(BORDER_COLORS)]
        
        bordered_img = Image.new('RGBA', bordered_size, border_color)
        bordered_img.paste(base_img, (border_width, border_width))
        
        # Add stickers
        draw = ImageDraw.Draw(bordered_img)
        num_stickers = random.randint(1, 3)
        
        try:
            font_large = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 30)
            font_medium = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 24)
            font_small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        for _ in range(num_stickers):
            sticker = random.choice(STICKERS)
            x = random.randint(20, bordered_size[0] - 100)
            y = random.randint(20, bordered_size[1] - 80)
            
            # Draw background if exists
            if sticker['bg']:
                bbox = draw.textbbox((0, 0), sticker['text'], font=font_medium)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                padding = 10
                draw.rectangle(
                    [x, y, x + text_width + padding * 2, y + text_height + padding * 2],
                    fill=sticker['bg']
                )
                draw.text((x + padding, y + padding), sticker['text'], 
                         fill=sticker['color'], font=font_medium)
            else:
                draw.text((x, y), sticker['text'], fill=sticker['color'], font=font_large)
        
        # Convert to RGB for JPEG
        final_img = bordered_img.convert('RGB')
        
        # Calculate shipping for this variation
        zone = zones[i % len(zones)]
        shipping_rate = get_shipping_rate(weight, zone)
        
        # Save to bytes
        buffer = io.BytesIO()
        final_img.save(buffer, format='JPEG', quality=95)
        img_bytes = buffer.getvalue()
        img_base64 = base64.b64encode(img_bytes).decode()
        
        variations.append({
            'image_data': img_base64,
            'border_color': border_color,
            'shipping_rate': shipping_rate,
            'zone': zone.title(),
            'variation_id': i + 1
        })
    
    return variations
