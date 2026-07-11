REGIONS: dict[str, dict[str, str]] = {
    "11110": {"name_ko": "종로구", "name_en": "Jongno-gu"},
    "11140": {"name_ko": "중구", "name_en": "Jung-gu"},
    "11170": {"name_ko": "용산구", "name_en": "Yongsan-gu"},
    "11200": {"name_ko": "성동구", "name_en": "Seongdong-gu"},
    "11215": {"name_ko": "광진구", "name_en": "Gwangjin-gu"},
    "11230": {"name_ko": "동대문구", "name_en": "Dongdaemun-gu"},
    "11260": {"name_ko": "중랑구", "name_en": "Jungnang-gu"},
    "11290": {"name_ko": "성북구", "name_en": "Seongbuk-gu"},
    "11305": {"name_ko": "강북구", "name_en": "Gangbuk-gu"},
    "11320": {"name_ko": "도봉구", "name_en": "Dobong-gu"},
    "11350": {"name_ko": "노원구", "name_en": "Nowon-gu"},
    "11380": {"name_ko": "은평구", "name_en": "Eunpyeong-gu"},
    "11410": {"name_ko": "서대문구", "name_en": "Seodaemun-gu"},
    "11440": {"name_ko": "마포구", "name_en": "Mapo-gu"},
    "11470": {"name_ko": "양천구", "name_en": "Yangcheon-gu"},
    "11500": {"name_ko": "강서구", "name_en": "Gangseo-gu"},
    "11530": {"name_ko": "구로구", "name_en": "Guro-gu"},
    "11545": {"name_ko": "금천구", "name_en": "Geumcheon-gu"},
    "11560": {"name_ko": "영등포구", "name_en": "Yeongdeungpo-gu"},
    "11590": {"name_ko": "동작구", "name_en": "Dongjak-gu"},
    "11620": {"name_ko": "관악구", "name_en": "Gwanak-gu"},
    "11650": {"name_ko": "서초구", "name_en": "Seocho-gu"},
    "11680": {"name_ko": "강남구", "name_en": "Gangnam-gu"},
    "11710": {"name_ko": "송파구", "name_en": "Songpa-gu"},
    "11740": {"name_ko": "강동구", "name_en": "Gangdong-gu"},
}


def is_valid_region(code: str) -> bool:
    return code in REGIONS
