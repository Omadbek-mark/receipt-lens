"""Display translations for ReceiptLens. Domain values stay canonical."""

from collections.abc import Callable, Mapping

import streamlit as st

UI_LANGUAGES = {"en": "English", "uz": "O‘zbekcha", "ko": "한국어"}

# Streamlit includes displayed options in widget identity. Carry selections across
# language changes so a relabelled widget keeps its canonical value.
OPTION_KEYS = (
    "workspace",
    "doc_source",
    "doc_language",
    "doc_mode",
    "receipt_section",
    "receipt_source",
    "receipt_language",
    "receipt_framing",
    "receipt_field_currency",
    "receipt_field_category",
    "receipt_filter_category",
    "receipt_translation_target",
)


def preserve_options() -> None:
    state = st.session_state
    for key in OPTION_KEYS:
        if key in state:
            state[key] = state[key]


def tr(message: str) -> str:
    return _translate(message, st.session_state.get("ui_language", "en"))


def option_labels(names: Mapping[str, str] | None = None) -> Callable[[str], str]:
    language = st.session_state.get("ui_language", "en")

    def label(value: str) -> str:
        return _translate(names[value] if names is not None else value, language)

    return label


def _translate(message: str, language: str) -> str:
    translations = MESSAGES.get(message)
    if translations and language in ("uz", "ko"):
        return translations[0 if language == "uz" else 1]
    return message


# Each pair contains Uzbek and Korean in that order.
MESSAGES = {
    "Workspace": ("Ish maydoni", "작업 공간"),
    "Receipt expenses": ("Chek xarajatlari", "영수증 지출"),
    "Document scanner": ("Hujjat skaneri", "문서 스캐너"),
    "Straighten a page. Read its text. Keep it local.": (
        "Sahifani tekislang va matnni qurilmangizda o‘qing.",
        "문서를 보정하고 기기에서 텍스트를 읽으세요.",
    ),
    "Your document": ("Hujjatingiz", "내 문서"),
    "Document source": ("Hujjat manbasi", "문서 원본"),
    "Upload an image": ("Rasm yuklash", "이미지 업로드"),
    "Try a sample": ("Namuna bilan sinash", "예제 사용"),
    "Document language": ("Hujjat tili", "문서 언어"),
    "Choose document language": ("Hujjat tilini tanlang", "문서 언어를 선택하세요"),
    "JPEG, PNG or HEIC": ("JPEG, PNG yoki HEIC", "JPEG, PNG 또는 HEIC"),
    "One page · up to 10 MB · up to 20 megapixels": (
        "Bitta sahifa · 10 MB va 20 megapikselgacha",
        "한 페이지 · 최대 10MB, 20메가픽셀",
    ),
    "An original synthetic example in the selected language.": (
        "Tanlangan tildagi sun’iy namuna.",
        "선택한 언어의 가상 예제입니다.",
    ),
    "Use original framing": ("Asl kadrdan foydalanish", "원본 구도 사용"),
    "Enable this if the detected document border is wrong.": (
        "Aniqlangan chegara xato bo‘lsa, belgilang.",
        "문서 테두리가 잘못 감지되면 선택하세요.",
    ),
    "Clear session": ("Sessiyani tozalash", "세션 초기화"),
    "Images are processed on this computer. No cloud OCR API or document database.": (
        "Rasmlar shu qurilmada qayta ishlanadi va bazaga yozilmaydi.",
        "이미지는 이 기기에서 처리되며 데이터베이스에 저장되지 않습니다.",
    ),
    "The first use of a language may download model files.": (
        "Til birinchi marta ishlatilganda model yuklanishi mumkin.",
        "언어를 처음 사용하면 모델 파일을 다운로드할 수 있습니다.",
    ),
    "The example image is missing. Upload an image instead.": (
        "Namuna topilmadi. Rasm yuklang.",
        "예제 이미지가 없습니다. 이미지를 업로드하세요.",
    ),
    "Upload a printed, single-column page or try a sample to get started.": (
        "Boshlash uchun bir ustunli bosma sahifa yuklang yoki namunani sinang.",
        "인쇄된 단일 열 문서를 업로드하거나 예제를 사용하세요.",
    ),
    "Scan and read text": ("Skanerlash va matnni o‘qish", "스캔하고 텍스트 읽기"),
    "Processing your document...": ("Hujjatga ishlov berilmoqda…", "문서 처리 중…"),
    "Original image": ("Asl rasm", "원본 이미지"),
    "Text reading complete.": ("Matn o‘qildi.", "텍스트 읽기가 완료되었습니다."),
    "Image processed.": ("Rasmga ishlov berildi.", "이미지 처리가 완료되었습니다."),
    "Original framing retained.": ("Asl kadr saqlandi.", "원본 구도를 유지했습니다."),
    "Document border detected and perspective corrected.": (
        "Hujjat chegarasi topildi va tasvir tekislandi.",
        "문서 테두리를 감지하고 원근을 보정했습니다.",
    ),
    "Input": ("Kirish rasmi", "입력"),
    "Original": ("Asl", "원본"),
    "Detected boundary": ("Aniqlangan chegara", "감지된 테두리"),
    "Scan": ("Skan", "스캔"),
    "Scan appearance": ("Skan ko‘rinishi", "스캔 모드"),
    "Color": ("Rangli", "컬러"),
    "Black and white": ("Oq-qora", "흑백"),
    "Recognized text": ("O‘qilgan matn", "인식된 텍스트"),
    "No text detected. Check the image quality and selected language, then retry.": (
        "Matn topilmadi. Rasm sifati va tanlangan tilni tekshirib, qayta urining.",
        "텍스트를 찾지 못했습니다. 이미지 품질과 선택한 언어를 확인한 후 다시 시도하세요.",
    ),
    "Review and edit the text": ("Matnni tekshirish va tahrirlash", "텍스트 검토 및 편집"),
    "OCR can miss characters and punctuation. Review the text before exporting.": (
        "OCR ayrim harf va "
        "tinish "
        "belgilarini "
        "o‘tkazishi "
        "mumkin. "
        "Eksportdan oldin "
        "matnni "
        "tekshiring.",
        "OCR이 글자나 문장 부호를 놓칠 수 있습니다. 내보내기 전에 확인하세요.",
    ),
    "Model confidence": ("Model ishonchi", "모델 신뢰도"),
    "These are model confidence scores, not measured accuracy. Text boxes refer to the image read by OCR.": (
        "Bu modelning ishonch ballari. Matn ramkalari OCR o‘qigan rasmga tegishli.",
        "모델의 신뢰도 점수입니다. 텍스트 영역은 OCR에 사용한 이미지 기준입니다.",
    ),
    "Text": ("Matn", "텍스트"),
    "Confidence": ("Ishonch", "신뢰도"),
    "Download": ("Yuklab olish", "다운로드"),
    "Download {kind}": ("{kind} yuklab olish", "{kind} 다운로드"),
    "After editing text or changing scan appearance, select Prepare downloads. The PDF contains the scan image; TXT contains your edited text.": (
        "Matn "
        "yoki "
        "skan "
        "ko‘rinishi "
        "o‘zgarsa, "
        "«Fayllarni "
        "tayyorlash»ni "
        "bosing. "
        "PDF’da "
        "rasm, "
        "TXT’da "
        "tahrirlangan "
        "matn "
        "bo‘ladi.",
        "텍스트나 "
        "스캔 "
        "모드를 "
        "바꾼 "
        "뒤 "
        "파일을 "
        "준비하세요. "
        "PDF에는 "
        "스캔 "
        "이미지, "
        "TXT에는 "
        "편집한 "
        "텍스트가 "
        "들어갑니다.",
    ),
    "Prepare downloads": ("Fayllarni tayyorlash", "파일 준비"),
    "Could not prepare downloads. Try again.": (
        "Fayllarni tayyorlab bo‘lmadi. Qayta urining.",
        "파일을 준비하지 못했습니다. 다시 시도하세요.",
    ),
    "Signed in as {username}": ("{username} hisobi faol", "{username}님으로 로그인했습니다"),
    "Sign out": ("Chiqish", "로그아웃"),
    "Sign in to save reviewed receipts and view your own expenses. Scanner-only mode is also available.": (
        "Cheklarni "
        "saqlash "
        "va "
        "xarajatlarni "
        "ko‘rish "
        "uchun "
        "kiring. "
        "Hujjat "
        "skaneridan "
        "hisobsiz "
        "foydalanish "
        "mumkin.",
        "영수증을 "
        "저장하고 "
        "내 "
        "지출을 "
        "보려면 "
        "로그인하세요. "
        "문서 "
        "스캐너는 "
        "로그인 "
        "없이 "
        "사용할 "
        "수 "
        "있습니다.",
    ),
    "Sign in": ("Kirish", "로그인"),
    "Create account": ("Hisob yaratish", "계정 만들기"),
    "Username": ("Foydalanuvchi nomi", "사용자 이름"),
    "Password": ("Parol", "비밀번호"),
    "Username or password was not accepted.": (
        "Foydalanuvchi nomi yoki parol xato.",
        "사용자 이름 또는 비밀번호가 올바르지 않습니다.",
    ),
    "Use a new username and a password of 5–128 characters. This local preview has no password-reset email.": (
        "Yangi "
        "foydalanuvchi "
        "nomi "
        "va "
        "5–128 "
        "belgili "
        "parol "
        "kiriting. "
        "Parolni "
        "email "
        "orqali "
        "tiklash "
        "hozircha "
        "mavjud "
        "emas.",
        "새 "
        "사용자 "
        "이름과 "
        "5~128자의 "
        "비밀번호를 "
        "입력하세요. "
        "이메일 "
        "비밀번호 "
        "재설정은 "
        "현재 "
        "제공되지 "
        "않습니다.",
    ),
    "New username": ("Yangi foydalanuvchi nomi", "새 사용자 이름"),
    "New password": ("Yangi parol", "새 비밀번호"),
    "Repeat password": ("Parolni takrorlang", "비밀번호 확인"),
    "Passwords must match.": ("Parollar bir xil bo‘lishi kerak.", "비밀번호가 일치해야 합니다."),
    "Review before saving": ("Saqlashdan oldin tekshiring", "저장 전 검토"),
    "OCR uses AI. Field and category suggestions use rules and may be wrong. Nothing is saved until you confirm.": (
        "OCR "
        "matnni "
        "AI "
        "yordamida "
        "o‘qiydi. "
        "Taklif "
        "qilingan "
        "maydon "
        "va "
        "toifalarni "
        "tekshiring. "
        "Tasdiqlaganingizdan "
        "keyin "
        "saqlanadi.",
        "OCR은 AI를 사용합니다. 제안된 항목과 카테고리를 확인하세요. 확인 후 저장됩니다.",
    ),
    "Evidence for field suggestions": ("Takliflar asosi", "항목 제안 근거"),
    "Confirm expense fields": ("Xarajat ma’lumotlarini tasdiqlash", "지출 정보 확인"),
    "This image has already been saved in your account.": (
        "Bu rasm hisobingizda saqlangan.",
        "이 이미지는 이미 내 계정에 저장되어 있습니다.",
    ),
    "Merchant / organization": ("Sotuvchi yoki tashkilot", "가맹점 또는 기관"),
    "Receipt date (YYYY-MM-DD)": ("Chek sanasi (YYYY-MM-DD)", "영수증 날짜 (YYYY-MM-DD)"),
    "Total amount": ("Jami summa", "합계 금액"),
    "Choose currency": ("Valyutani tanlang", "통화를 선택하세요"),
    "Currency": ("Valyuta", "통화"),
    "Category": ("Toifa", "카테고리"),
    "Note (optional)": ("Izoh (ixtiyoriy)", "메모 (선택)"),
    "I checked the merchant, date, amount and currency.": (
        "Sotuvchi, sana, summa va valyutani tekshirdim.",
        "가맹점, 날짜, 금액, 통화를 확인했습니다.",
    ),
    "If a similar expense exists, save this as a separate purchase.": (
        "O‘xshash xarajat bo‘lsa ham, buni alohida xarid sifatida saqlash.",
        "비슷한 지출이 있어도 별도 구매로 저장합니다.",
    ),
    "Saving stores the image, OCR text and confirmed fields in your account. You can delete the entry from My expenses.": (
        "Saqlashda "
        "rasm, "
        "OCR "
        "matni "
        "va "
        "tasdiqlangan "
        "ma’lumotlar "
        "hisobingizga "
        "yoziladi. "
        "Yozuvni "
        "«Xarajatlarim»dan "
        "o‘chirishingiz "
        "mumkin.",
        "이미지, OCR 텍스트, 확인한 정보가 계정에 저장됩니다. 내 지출에서 삭제할 수 있습니다.",
    ),
    "Save expense": ("Xarajatni saqlash", "지출 저장"),
    "Check the receipt fields and confirm before saving.": (
        "Saqlashdan oldin chek ma’lumotlarini tekshirib, tasdiqlang.",
        "저장하기 전에 영수증 정보를 검토하고 확인하세요.",
    ),
    "A matching merchant/date/amount already exists. Check it, or confirm this is a separate purchase.": (
        "Sotuvchi, "
        "sana "
        "va "
        "summa "
        "bir "
        "xil "
        "yozuv "
        "bor. "
        "Uni "
        "tekshiring "
        "yoki "
        "bu "
        "boshqa "
        "xarid "
        "ekanini "
        "tasdiqlang.",
        "가맹점, 날짜, 금액이 일치하는 기록이 있습니다. 확인하거나 별도 구매임을 표시하세요.",
    ),
    "Expense saved. Open My expenses to view it.": (
        "Xarajat saqlandi. Uni «Xarajatlarim»da ko‘ring.",
        "지출이 저장되었습니다. 내 지출에서 확인하세요.",
    ),
    "Receipt source": ("Chek manbasi", "영수증 원본"),
    "Upload a receipt": ("Chek yuklash", "영수증 업로드"),
    "Try a demo receipt": ("Namuna chekni sinash", "예제 영수증 사용"),
    "Language printed on receipt": ("Chek yozilgan til", "영수증에 적힌 언어"),
    "Choose the language printed on the receipt": (
        "Chek yozilgan tilni tanlang",
        "영수증에 적힌 언어를 선택하세요",
    ),
    "Choose the original receipt language. To translate it, use Translate receipt text after OCR.": (
        "Chekning "
        "asl "
        "tilini "
        "tanlang. "
        "O‘qilgach, "
        "«Chek "
        "matnini "
        "tarjima "
        "qilish» "
        "bo‘limidan "
        "foydalaning.",
        "영수증 원문 언어를 선택하세요. OCR 후 영수증 텍스트 번역에서 번역할 수 있습니다.",
    ),
    "Receipt JPEG, PNG or HEIC": (
        "Chek rasmi (JPEG, PNG yoki HEIC)",
        "영수증 이미지 (JPEG, PNG 또는 HEIC)",
    ),
    "Receipt framing": ("Chek kadri", "영수증 구도"),
    "Automatic": ("Avtomatik", "자동"),
    "Manual crop": ("Qo‘lda qirqish", "수동 자르기"),
    "Choose Korean for a Korean receipt. No language model is selected by default.": (
        "Koreyscha chek uchun koreys tilini tanlang. Chek tilini o‘zingiz belgilang.",
        "한국어 영수증은 한국어를 선택하세요. 영수증 언어를 직접 지정해야 합니다.",
    ),
    "One receipt · JPEG/PNG/HEIC · up to 10 MB and 20 megapixels": (
        "Bitta chek · JPEG/PNG/HEIC · 10 MB va 20 megapikselgacha",
        "영수증 한 장 · JPEG/PNG/HEIC · 최대 10MB, 20메가픽셀",
    ),
    "Read receipt": ("Chekni o‘qish", "영수증 읽기"),
    "Reading your receipt...": ("Chek o‘qilmoqda…", "영수증 읽는 중…"),
    "My expenses": ("Xarajatlarim", "내 지출"),
    "Dates come from reviewed receipts. Amounts in different currencies are never combined or converted.": (
        "Sanalar tasdiqlangan cheklardan olinadi. Har bir valyuta jami alohida hisoblanadi.",
        "날짜는 검토한 영수증을 기준으로 합니다. 통화별 합계를 따로 표시합니다.",
    ),
    "From": ("Boshlanish", "시작일"),
    "To": ("Tugash", "종료일"),
    "Filter category": ("Toifa bo‘yicha saralash", "카테고리 필터"),
    "All": ("Barchasi", "전체"),
    "No expenses match these filters. Adjust the dates or save a reviewed receipt.": (
        "Bu filtrlarga mos xarajat yo‘q. Sanalarni o‘zgartiring yoki tekshirilgan chekni saqlang.",
        "필터에 맞는 지출이 없습니다. 날짜를 바꾸거나 검토한 영수증을 저장하세요.",
    ),
    "Totals for the selected filters": ("Tanlangan filtrlar bo‘yicha jami", "선택한 필터의 합계"),
    "Monthly totals for the selected filters": (
        "Tanlangan filtrlar bo‘yicha oylik jami",
        "선택한 필터의 월별 합계",
    ),
    "Date": ("Sana", "날짜"),
    "Merchant": ("Sotuvchi", "가맹점"),
    "Amount": ("Summa", "금액"),
    "Note": ("Izoh", "메모"),
    "Month": ("Oy", "월"),
    "Total": ("Jami", "합계"),
    "Export filtered CSV": ("Saralangan CSV’ni yuklab olish", "필터 결과 CSV 내보내기"),
    "View saved receipt": ("Saqlangan chekni ko‘rish", "저장된 영수증 보기"),
    "Saved image and OCR text": ("Saqlangan rasm va OCR matni", "저장된 이미지와 OCR 텍스트"),
    "Delete this expense and its saved receipt image.": (
        "Ushbu xarajat va unga biriktirilgan chek rasmini o‘chirish.",
        "이 지출과 저장된 영수증 이미지를 삭제합니다.",
    ),
    "Delete expense": ("Xarajatni o‘chirish", "지출 삭제"),
    "Read a receipt, check the fields, and keep a personal expense record.": (
        "Chekni o‘qing, ma’lumotlarni tekshiring va xarajatlaringizni saqlang.",
        "영수증을 읽고 정보를 확인한 뒤 개인 지출을 기록하세요.",
    ),
    "Expense workspace": ("Xarajatlar bo‘limi", "지출 관리"),
    "Add receipt": ("Chek qo‘shish", "영수증 추가"),
    "Expense storage is unavailable. Check the local data directory and retry.": (
        "Xarajatlar "
        "omboriga ulanib "
        "bo‘lmadi. Mahalliy "
        "ma’lumotlar "
        "papkasini "
        "tekshirib, qayta "
        "urining.",
        "지출 저장소를 사용할 수 없습니다. 로컬 데이터 폴더를 확인하고 다시 시도하세요.",
    ),
    "Receipt text": ("Chek matni", "영수증 텍스트"),
    "Aligned text": ("Tartiblangan matn", "정렬된 텍스트"),
    "Select a line": ("Qatorni tanlash", "줄 선택"),
    "Approximate column spacing from the image. Recognition errors may remain.": (
        "Ustun oralig‘i rasm asosida taxminan tiklandi. Matnda o‘qish xatolari bo‘lishi mumkin.",
        "이미지를 바탕으로 열 간격을 추정했습니다. 인식 오류가 남을 수 있습니다.",
    ),
    "Line": ("Qator", "줄"),
    "Select a row to highlight that line in the image.": (
        "Rasmda belgilash uchun qatorni tanlang.",
        "이미지에서 강조할 줄을 선택하세요.",
    ),
    "No text detected. Check the selected language or crop the receipt area.": (
        "Matn topilmadi. Tilni tekshiring yoki chek atrofini qirqing.",
        "텍스트를 찾지 못했습니다. 선택한 언어를 확인하거나 영수증 영역을 잘라보세요.",
    ),
    "Image read by OCR": ("OCR o‘qigan rasm", "OCR에 사용한 이미지"),
    "Original image and selected framing": (
        "Asl rasm va tanlangan kadr",
        "원본 이미지와 선택한 구도",
    ),
    "Move the range handles to keep only the receipt. The green box shows the selected area.": (
        "Faqat chek qolishi uchun slayderlarni suring. Yashil ramka tanlangan joyni ko‘rsatadi.",
        "슬라이더를 움직여 영수증 영역을 남기세요. 초록색 상자가 선택 영역입니다.",
    ),
    "Horizontal crop (%)": ("Eniga qirqish (%)", "가로 자르기 (%)"),
    "Vertical crop (%)": ("Bo‘yiga qirqish (%)", "세로 자르기 (%)"),
    "Keep at least 32 pixels in each direction.": (
        "Har ikki yo‘nalishda kamida 32 piksel qoldiring.",
        "가로와 세로를 각각 최소 32픽셀로 유지하세요.",
    ),
    "Manual crop preview": ("Qo‘lda qirqish ko‘rinishi", "수동 자르기 미리보기"),
    "Translate receipt text": ("Chek matnini tarjima qilish", "영수증 텍스트 번역"),
    "Translation uses Google Gemini. Only the text below is sent after you request it; the receipt image is not sent. Source OCR and saved expense values remain separate.": (
        "Tarjima "
        "Google "
        "Gemini "
        "orqali "
        "bajariladi. "
        "Tugmani "
        "bosganingizda "
        "faqat "
        "quyidagi "
        "matn "
        "yuboriladi. "
        "OCR "
        "natijasi "
        "va "
        "saqlangan "
        "xarajatlar "
        "alohida "
        "qoladi.",
        "번역에는 "
        "Google "
        "Gemini를 "
        "사용합니다. "
        "요청 "
        "시 "
        "아래 "
        "텍스트만 "
        "전송합니다. "
        "OCR "
        "원문과 "
        "저장된 "
        "지출 "
        "정보는 "
        "별도로 "
        "유지됩니다.",
    ),
    "Gemini may make mistakes. On the free API tier, submitted content may be used to improve Google products. Use non-private demo text.": (
        "Gemini "
        "xato "
        "qilishi "
        "mumkin. "
        "Bepul "
        "API’ga "
        "yuborilgan "
        "kontent "
        "Google "
        "mahsulotlarini "
        "yaxshilashda "
        "ishlatilishi "
        "mumkin. "
        "Shaxsiy "
        "ma’lumotsiz "
        "demo "
        "matndan "
        "foydalaning.",
        "Gemini가 "
        "틀릴 "
        "수 "
        "있습니다. "
        "무료 "
        "API에 "
        "제출한 "
        "내용은 "
        "Google "
        "제품 "
        "개선에 "
        "사용될 "
        "수 "
        "있습니다. "
        "개인정보가 "
        "없는 "
        "예제를 "
        "사용하세요.",
    ),
    "Translation is not available on this installation yet. Server setup is required.": (
        "Tarjima uchun server sozlamalarini tayyorlash kerak.",
        "번역을 사용하려면 서버 설정이 필요합니다.",
    ),
    "Review text to translate": ("Tarjima qilinadigan matnni tekshirish", "번역할 텍스트 검토"),
    "Translate to": ("Tarjima tili", "번역 대상 언어"),
    "Choose translation language": ("Tarjima tilini tanlang", "번역할 언어를 선택하세요"),
    "Send this text to Google Gemini.": (
        "Bu matnni Google Gemini’ga yuborishga roziman.",
        "이 텍스트를 Google Gemini로 전송하는 데 동의합니다.",
    ),
    "Translate text": ("Matnni tarjima qilish", "텍스트 번역"),
    "Choose a target language and consent before translating.": (
        "Tarjimadan oldin tilni tanlang va rozilik bildiring.",
        "번역 대상 언어를 선택하고 전송에 동의하세요.",
    ),
    "Please wait a moment before another translation request.": (
        "Keyingi tarjima so‘rovidan oldin biroz kuting.",
        "다음 번역을 요청하기 전에 잠시 기다리세요.",
    ),
    "Translating selected text...": (
        "Tanlangan matn tarjima qilinmoqda…",
        "선택한 텍스트 번역 중…",
    ),
    "Translation": ("Tarjima", "번역"),
    "Download translation TXT": ("Tarjimani TXT formatida yuklab olish", "번역 TXT 다운로드"),
    "English": ("Inglizcha", "영어"),
    "Uzbek (Latin)": ("O‘zbekcha (lotin)", "우즈베크어 (라틴 문자)"),
    "Korean": ("Koreyscha", "한국어"),
    "Username: use 3–32 lowercase letters, digits or underscores.": (
        "Foydalanuvchi nomiga 3–32 ta kichik lotin harfi, raqam yoki pastki chiziq kiriting.",
        "사용자 이름은 소문자 영문, 숫자 또는 밑줄 3~32자로 입력하세요.",
    ),
    "Use a password between 5 and 128 characters.": (
        "5–128 belgili parol kiriting.",
        "비밀번호를 5~128자로 입력하세요.",
    ),
    "Choose a different username.": (
        "Boshqa foydalanuvchi nomini tanlang.",
        "다른 사용자 이름을 선택하세요.",
    ),
    "Too many attempts. Try again in 5 minutes.": (
        "Urinishlar soni oshib ketdi. 5 daqiqadan keyin qayta urining.",
        "시도 횟수를 초과했습니다. 5분 후 다시 시도하세요.",
    ),
    "Waiting for the document processor": (
        "Hujjatga ishlov berish navbati kutilmoqda",
        "문서 처리 대기 중",
    ),
    "Preparing document": ("Hujjat tayyorlanmoqda", "문서 준비 중"),
    "Loading OCR model": ("OCR modeli yuklanmoqda", "OCR 모델 불러오는 중"),
    "Reading document text": ("Hujjat matni o‘qilmoqda", "문서 텍스트 읽는 중"),
    "Image exceeds the 10 MB file limit.": (
        "Rasm hajmi 10 MB dan oshgan.",
        "이미지가 10MB 제한을 초과했습니다.",
    ),
    "Image exceeds the 20 megapixel limit.": (
        "Rasm 20 megapiksel chegarasidan oshgan.",
        "이미지가 20메가픽셀 제한을 초과했습니다.",
    ),
    "Only JPEG, PNG and HEIC/HEIF images are supported.": (
        "JPEG, PNG va HEIC/HEIF rasmlarini yuklang.",
        "JPEG, PNG, HEIC/HEIF 이미지를 업로드하세요.",
    ),
    "The start date must be before the end date.": (
        "Boshlanish sanasi tugash sanasidan oldin bo‘lishi kerak.",
        "시작일은 종료일보다 앞서야 합니다.",
    ),
    "Enter a valid date in YYYY-MM-DD format.": (
        "Sanani YYYY-MM-DD shaklida kiriting.",
        "날짜를 YYYY-MM-DD 형식으로 입력하세요.",
    ),
    "Choose USD, UZS or KRW.": ("USD, UZS yoki KRW ni tanlang.", "USD, UZS 또는 KRW를 선택하세요."),
    "Check the amount.": ("Summani tekshiring.", "금액을 확인하세요."),
    "Check the amount separators.": (
        "Summadagi ajratish belgilarini tekshiring.",
        "금액의 구분 기호를 확인하세요.",
    ),
    "Check the amount grouping spaces.": (
        "Summadagi bo‘shliqlarni tekshiring.",
        "금액의 공백을 확인하세요.",
    ),
    "Check the amount and currency decimal places.": (
        "Summa va valyutaning kasr xonalarini tekshiring.",
        "금액과 통화의 소수 자릿수를 확인하세요.",
    ),
    "Enter a positive amount using digits and decimal/group separators.": (
        "Musbat summani raqam va ajratish belgilari bilan kiriting.",
        "숫자와 소수점 또는 자릿수 구분 기호로 양수 금액을 입력하세요.",
    ),
    "Translation limit reached. Please retry later.": (
        "Tarjima limiti tugadi. Keyinroq qayta urining.",
        "번역 한도에 도달했습니다. 나중에 다시 시도하세요.",
    ),
    "The translation service is unavailable. Please retry later.": (
        "Tarjima xizmati ishlamayapti. Keyinroq qayta urining.",
        "번역 서비스를 사용할 수 없습니다. 나중에 다시 시도하세요.",
    ),
    "The translation service returned an unreadable response.": (
        "Tarjima xizmatidan yaroqsiz javob keldi.",
        "번역 서비스에서 읽을 수 없는 응답이 왔습니다.",
    ),
    "Food": ("Oziq-ovqat", "식비"),
    "Transport": ("Transport", "교통"),
    "Shopping": ("Xaridlar", "쇼핑"),
    "Health": ("Sog‘liq", "건강"),
    "Utilities": ("Kommunal xizmatlar", "공과금"),
    "Other": ("Boshqa", "기타"),
    "Education": ("Ta’lim", "교육"),
    "No document boundary found. The original image is retained.": (
        "Hujjat chegarasi topilmadi. Asl rasm saqlandi.",
        "문서 테두리를 찾지 못해 원본 이미지를 유지했습니다.",
    ),
    "Cannot read this image. Upload a valid JPEG, PNG or HEIC/HEIF.": (
        "Rasmni ochib bo‘lmadi. Yaroqli JPEG, PNG yoki HEIC/HEIF yuklang.",
        "이미지를 읽을 수 없습니다. 올바른 JPEG, PNG 또는 HEIC/HEIF를 업로드하세요.",
    ),
    "The document processor is busy. Please retry shortly.": (
        "Hujjatga ishlov berish band. Birozdan keyin qayta urining.",
        "문서 처리기가 사용 중입니다. 잠시 후 다시 시도하세요.",
    ),
    "Could not load the OCR model. Check the installation and model download connection.": (
        "OCR modeli yuklanmadi. O‘rnatish va tarmoq ulanishini tekshiring.",
        "OCR 모델을 불러오지 못했습니다. 설치와 네트워크 연결을 확인하세요.",
    ),
    "Could not read the document. Try a clearer image or retry processing.": (
        "Hujjatni o‘qib bo‘lmadi. Tiniqroq rasm yuklang yoki qayta urining.",
        "문서를 읽지 못했습니다. 더 선명한 이미지로 다시 시도하세요.",
    ),
    "This image is already saved in your account.": (
        "Bu rasm hisobingizda saqlangan.",
        "이 이미지는 이미 내 계정에 저장되어 있습니다.",
    ),
    "Check merchant, category, currency and note length.": (
        "Sotuvchi, toifa, valyuta va izoh uzunligini tekshiring.",
        "가맹점, 카테고리, 통화, 메모 길이를 확인하세요.",
    ),
    "Receipt image or text is too large or missing.": (
        "Chek rasmi yoki matni yo‘q yoki hajmi juda katta.",
        "영수증 이미지나 텍스트가 없거나 너무 큽니다.",
    ),
    "Could not save this expense. Sign in again.": (
        "Xarajatni saqlab bo‘lmadi. Qayta kiring.",
        "지출을 저장하지 못했습니다. 다시 로그인하세요.",
    ),
    "Image must be at least 32 pixels per side and at most 20 megapixels.": (
        "Rasmning har bir tomoni "
        "kamida 32 piksel va "
        "umumiy hajmi ko‘pi "
        "bilan 20 megapiksel "
        "bo‘lsin.",
        "이미지의 각 변은 32픽셀 이상이고 전체는 20메가픽셀 이하여야 합니다.",
    ),
    "Select a crop inside the image, at least 32 pixels per side.": (
        "Rasm ichida har tomoni kamida 32 piksel bo‘lgan sohani tanlang.",
        "이미지 안에서 각 변이 32픽셀 이상인 영역을 선택하세요.",
    ),
    "Could not reach the translation service. Please retry later.": (
        "Tarjima xizmatiga ulanib bo‘lmadi. Keyinroq qayta urining.",
        "번역 서비스에 연결하지 못했습니다. 나중에 다시 시도하세요.",
    ),
    "Translation is unavailable. The server configuration needs checking.": (
        "Tarjima ishlamayapti. Server sozlamalarini tekshiring.",
        "번역을 사용할 수 없습니다. 서버 설정을 확인하세요.",
    ),
    "The server translation model needs checking.": (
        "Serverdagi tarjima modelini tekshiring.",
        "서버의 번역 모델을 확인하세요.",
    ),
    "Choose a different supported target language.": (
        "Boshqa tarjima tilini tanlang.",
        "지원하는 다른 번역 대상 언어를 선택하세요.",
    ),
    "Translation is not available on this installation yet.": (
        "Tarjima hozircha mavjud emas.",
        "현재 설정에서 번역을 사용할 수 없습니다.",
    ),
    "Translate at most 128 lines and 5,000 characters at a time.": (
        "Bir vaqtda ko‘pi bilan 128 qator va 5 000 belgini tarjima qiling.",
        "한 번에 최대 128줄, 5,000자까지 번역할 수 있습니다.",
    ),
    "Remove reserved placeholder text before translating.": (
        "Tarjimadan oldin tizimning maxsus belgilarini olib tashlang.",
        "번역하기 전에 예약된 자리 표시자를 제거하세요.",
    ),
    "Select fewer lines before translating.": (
        "Tarjima uchun kamroq qator tanlang.",
        "번역할 줄 수를 줄이세요.",
    ),
    "Could not preserve receipt numbers. No translation was accepted.": (
        "Chek raqamlari saqlanmadi. Tarjima bekor qilindi.",
        "영수증 숫자를 보존하지 못해 번역을 적용하지 않았습니다.",
    ),
    "Translation changed receipt numbers. No translation was accepted.": (
        "Tarjima chek raqamlarini o‘zgartirdi. Natija bekor qilindi.",
        "번역에서 영수증 숫자가 바뀌어 결과를 적용하지 않았습니다.",
    ),
    "Explicit currency marker in receipt text.": (
        "Chek matnida valyuta ko‘rsatilgan.",
        "영수증 텍스트에 통화 표시가 있습니다.",
    ),
    "Check merchant: missing or ambiguous evidence.": (
        "Sotuvchini tekshiring. Ma’lumot yetishmaydi yoki noaniq.",
        "가맹점을 확인하세요. 정보가 없거나 모호합니다.",
    ),
    "Check date: missing or ambiguous evidence.": (
        "Sanani tekshiring. Ma’lumot yetishmaydi yoki noaniq.",
        "날짜를 확인하세요. 정보가 없거나 모호합니다.",
    ),
    "Check total: missing or ambiguous evidence.": (
        "Jami summani tekshiring. Ma’lumot yetishmaydi yoki noaniq.",
        "합계를 확인하세요. 정보가 없거나 모호합니다.",
    ),
    "Check currency: missing or ambiguous evidence.": (
        "Valyutani tekshiring. Ma’lumot yetishmaydi yoki noaniq.",
        "통화를 확인하세요. 정보가 없거나 모호합니다.",
    ),
}
