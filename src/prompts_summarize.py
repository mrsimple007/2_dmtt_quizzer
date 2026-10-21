# Available languages with flags
LANGUAGES = {
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Russian",
    "uz": "🇺🇿 Uzbek"
}

# Quiz types
QUIZ_TYPES = {
    "mc": "Multiple Choice",
    "oe": "Open Ended"
}


OE_QUIZ_PROMPT="""
You are an expert educational content creator specializing in creating meaningful open-ended questions about real-world topics.

CRITICAL RULES:
1. Generate questions ABOUT the topic/subject mentioned in the text, NOT about the text itself
2. If the text is just a topic name, use your knowledge to create educational questions about that topic
3. NEVER create meta-questions about the quiz format or text structure
4. Questions should require thoughtful answers demonstrating real understanding

EXAMPLE - WRONG ❌:
Topic: "O'zbekiston Respublikasi"
Bad Question: "What format is this quiz in?"

EXAMPLE - CORRECT ✅:
Topic: "O'zbekiston Respublikasi"
Good Question: "Explain the significance of Uzbekistan's location on the ancient Silk Road."
Good Question: "Describe the main challenges facing the Aral Sea and their causes."

Instructions:
- Analyze the text/topic carefully
- If it's a short topic/keyword, use your knowledge to create questions about that subject
- Create exactly {num_questions} short open-ended questions that test real understanding
- Each answer should be 2-3 sentences providing meaningful educational content
- Use the same language as the input text: {doc_language}
- Questions should encourage critical thinking about the topic

Output format (strict JSON):
{{
  "questions": [
    {{
      "question": "Thoughtful question about the topic",
      "answer": "2-3 sentence answer with real educational content"
    }}
  ]
}}

Return ONLY the JSON object, no additional text.




"""


MCH_QUIZ_PROMPT="""
You are an expert educational content creator specializing in creating meaningful quizzes about real-world topics.

CRITICAL RULES:
1. Generate questions ABOUT the topic/subject mentioned in the text, NOT about the text itself
2. If the text is just a topic name (e.g., "O'zbekiston Respublikasi"), research your knowledge and create educational questions about that topic
3. NEVER create meta-questions about the quiz format, number of options, or the text structure
4. Create substantive educational questions that test real knowledge about the subject

EXAMPLE - WRONG ❌:
Topic: "O'zbekiston Respublikasi"
Bad Question: "What language is used in the text?" 
Bad Question: "How many questions does this quiz contain?"

EXAMPLE - CORRECT ✅:
Topic: "O'zbekiston Respublikasi"
Good Question: "What is the capital city of Uzbekistan?"
Good Question: "In which year did Uzbekistan gain independence?"
Good Question: "Which sea has been significantly affected by environmental issues in Uzbekistan?"

Instructions:
- Analyze the text/topic carefully
- If it's a short topic/keyword, use your knowledge to create educational questions about that subject
- Create exactly {num_questions} multiple choice questions with REAL educational value
- Each question must have 4 answer options, with only one correct answer
- IMPORTANT: Distribute correct answers evenly among options A, B, C, D (don't always make option C correct)
- Make distractors plausible but clearly incorrect to those who know the topic
- Use the same language as the input text: {doc_language}
- Questions should test genuine knowledge, not trivial or meta information

MANDATORY: Write a proper title that reflects the TOPIC (e.g., "Geography of Uzbekistan Quiz", not "O'zbekiston Respublikasi Quiz")

Output format (strict JSON):
{{
  "title": "Descriptive quiz title about the actual topic in {doc_language}",
  "summary": "2-3 sentence summary about what the quiz covers in {doc_language}",
  "questions": [
    {{
      "question": "Educational question about the topic",
      "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
      "correct_answer": "Correct option text (must exactly match one of the options)"
    }}
  ]
}}

Return ONLY the JSON object, no additional text.


"""

QUIZ_INFO_TRANSLATIONS = {
    'en': {
        'ask_quiz_info': (
            "📝 *Add Quiz Information (Optional)*\n\n"
            "You can add a title and description for your quiz.\n"
            "This will be shown to users before they start.\n\n"
            "Format:\n"
            "`Title: Your Quiz Title\n"
            "Description: Brief description of the quiz`\n\n"
            "Or tap Skip to continue without adding information."
        ),
        'skip_quiz_info': "⏭️ Skip",
        'quiz_info_received': "✅ Quiz information saved:\n\n{info}",
        'quiz_config': "📋 *Quiz Configuration*",
               'quiz_info_label': 'Quiz Info',
        'type': "📝 *Type:*",
        'questions': "🔢 *Questions:*",
        'time_per_question': "⏱️ *Time per question:*",
        'content_preview': "📄 *Content Preview:*",
        'ready_generate': "Ready to generate your quiz?",
        'generate_quiz': "✅ Generate Quiz",
        'change_questions': "🔢 Change Questions",
        'change_time': "⏱️ Change Time",
        'back_to_menu': "🔙 Back to Main Menu",
        'no_time_limit': "No Time Limit",
        'multiple_choice': "Multiple Choice",
        'open_ended': "Open Ended",
        "change_quiz_info": "📝 Change Quiz Info"
    },
    'uz': {
        'ask_quiz_info': (
            "📝 *Quiz Ma'lumotini Qo'shish (Ixtiyoriy)*\n\n"
            "Quizngiz uchun sarlavha va tavsif qo'shishingiz mumkin.\n"
            "Bu yerda quiz nomi, kanal linki va hokazolarni kiritish mumkin. Bu foydalanuvchilarga quiz boshlanishidan oldin ko'rsatiladi. \n\n"
            "Misol:\n"
            "`Ingliz tilidan quiz: SimpleLearn jamoasi (@SimpleLearnUz)\n"
            "Tavsif: Quiz haqida qisqacha ma'lumot`\n\n"
            "Yoki ma'lumot qo'shmasdan davom etish uchun O'tkazib yuborish tugmasini bosing."
        ),
        'skip_quiz_info': "⏭️ O'tkazib yuborish",
                'quiz_info_label': "Quiz Ma'lumoti",
        'quiz_info_received': "✅ Quiz ma'lumoti saqlandi:\n\n{info}",
        'quiz_config': "📋 *Quiz Sozlamalari*",
        'type': "📝 *Turi:*",
        'questions': "🔢 *Savollar:*",
        'time_per_question': "⏱️ *Har bir savol uchun vaqt:*",
        'content_preview': "📄 *Quiz mavzusi ko'rinishi:*",
        'ready_generate': "Quizni yaratishga tayyormisiz?",
        'generate_quiz': "✅ Quiz Yaratish",
        'change_questions': "🔢 Savollar sonini o'zgartirish",
        'change_time': "⏱️ Quiz Vaqtini O'zgartirish",
        'back_to_menu': "🔙 Asosiy Menyuga Qaytish",
        'no_time_limit': "Vaqt Cheklovsiz",
        'multiple_choice': "Ko'p Tanlovli",
        'open_ended': "Ochiq Javobli",
        "change_quiz_info": "📝 Quiz Ma'lumotini O'zgartirish"
    },
    'ru': {
        'ask_quiz_info': (
            "📝 *Добавить Информацию о Викторине (Необязательно)*\n\n"
            "Вы можете добавить название и описание для вашей викторины.\n"
            "Это будет показано пользователям перед началом.\n\n"
            "Формат:\n"
            "`Название: Название Викторины\n"
            "Описание: Краткое описание викторины`\n\n"
            "Или нажмите Пропустить, чтобы продолжить без добавления информации."
        ),
        'skip_quiz_info': "⏭️ Пропустить",
                'quiz_info_label': 'Информация о Викторине',
        'quiz_info_received': "✅ Информация о викторине сохранена:\n\n{info}",
        'quiz_config': "📋 *Настройки Викторины*",
        'type': "📝 *Тип:*",
        'questions': "🔢 *Вопросы:*",
        'time_per_question': "⏱️ *Время на вопрос:*",
        'content_preview': "📄 *Предварительный Просмотр:*",
        'ready_generate': "Готовы создать викторину?",
        'generate_quiz': "✅ Создать Викторину",
        'change_questions': "🔢 Изменить Вопросы",
        'change_time': "⏱️ Изменить Время",
        'back_to_menu': "🔙 Вернуться в Главное Меню",
        'no_time_limit': "Без Ограничения Времени",
        'multiple_choice': "Множественный Выбор",
        'open_ended': "Открытый Ответ",
        "change_quiz_info": "📝 Изменить Информацию о Викторине"
    }
}

COUNTDOWN_TRANSLATIONS = {
    'en': {
        'ready': '3️⃣ <b>Are you ready?</b>',
        'set': '2️⃣ <b>Get set...</b>',
        'go': '1️⃣ <b>Go!</b>'
    },
    'uz': {
        'ready': '3️⃣ <b>Tayyormisiz?</b>',
        'set': '2️⃣ <b>Quiz boshlanyapti...</b>',
        'go': '1️⃣ <b>Boshladik!</b>'
    },
    'ru': {
        'ready': '3️⃣ <b>Вы готовы?</b>',
        'set': '2️⃣ <b>Приготовьтесь...</b>',
        'go': '1️⃣ <b>Начали!</b>'
    }
}

PAUSE_TRANSLATIONS = {
    'en': {
        'paused': '⏸️ <b>Quiz Paused</b>\n\nYou haven\'t answered the last 2 questions.\n\nDo you want to continue or stop the quiz?',
        'continue': '▶️ Continue',
        'stop': '🛑 Stop Quiz',
        'resumed': '▶️ <b>Quiz Resumed</b>\n\nContinuing with next question...',
        'stopped': '🛑 <b>Quiz Stopped</b>\n\nThank you for participating!'
    },
    'uz': {
        'paused': '⏸️ <b>Quiz to\'xtatildi</b>\n\nSiz oxirgi 2 ta savolga javob bermadingiz.\n\nDavom ettirishni yoki to\'xtatishni xohlaysizmi?',
        'continue': '▶️ Davom etish',
        'stop': '🛑 To\'xtatish',
        'resumed': '▶️ <b>Quiz davom ettirildi</b>\n\nKeyingi savolga o\'tilmoqda...',
        'stopped': '🛑 <b>Quiz to\'xtatildi</b>\n\nIshtirok etganingiz uchun rahmat!'
    },
    'ru': {
        'paused': '⏸️ <b>Квиз приостановлена</b>\n\nВы не ответили на последние 2 вопроса.\n\nПродолжить или остановить викторину?',
        'continue': '▶️ Продолжить',
        'stop': '🛑 Остановить',
        'resumed': '▶️ <b>Квиз возобновлена</b>\n\nПереходим к следующему вопросу...',
        'stopped': '🛑 <b>Квиз остановлена</b>\n\nСпасибо за участие!'
    }
}

INSUFFICIENT_BALANCE_TRANSLATIONS = {
    "en": {
        "insufficient_balance": """❌ *Insufficient Balance*

*Current Balance:* {current_balance:,} UZS
*Required:* {required:,} UZS

Please top up your balance to continue.""",
        "topup_button": "💰 Top Up Balance",
        "share_earn": "🔗 Share & Earn"
    },
    "uz": {
        "insufficient_balance": """❌ *Balans yetarli emas*

*Joriy balans:* {current_balance:,} UZS
*Kerak:* {required:,} UZS

Davom etish uchun balansingizni to'ldiring.""",
        "topup_button": "💰 Balansni to'ldirish",
        "share_earn": "🔗 Ulashing va bepul quiz"
    },
    "ru": {
        "insufficient_balance": """❌ *Недостаточно средств*

*Текущий баланс:* {current_balance:,} UZS
*Требуется:* {required:,} UZS

Пополните баланс, чтобы продолжить.""",
        "topup_button": "💰 Пополнить баланс",
        "share_earn": "🔗 Поделиться и заработать"
    }
}

# Translations
TRANSLATIONS = {
    "en": {
"welcome": "🌟 *Welcome to SimpleQuizzer! Your AI Learning Companion* 🌟\n\n📚 *I'm here to help you learn through interactive quizzes!* ✨\n\n*Just share any of these with me:*\n• 📄 PDF documents\n• 📝 Word files (.docx)\n• 📃 Text files (.txt)\n• 🔗 Article URLs\n• 💭 Text passages\n• 🎤 Audio recordings\n• 🎥 Video content\n\n*I'll transform them into engaging quizzes to test your knowledge!* 🎯\n\n *Our new bot generates for you AI quizzes: @SimplePresentation_maker_bot*",
        "choose_language": "🌍 *Let's Get Started!*\n\n*Please select your preferred language:*\n\n🇬🇧 *English - Choose your language*\n🇷🇺 *Русский - Выберите ваш язык*\n🇺🇿 *O'zbek - Tilingizni tanlang*",

        "language_selected": "✅ *Perfect! English has been set as your language!*\n\n*You're all set to start your learning journey with SimpleQuizzer! Start the bot with /start* 🚀",
        "help": "📚 *SimpleQuizzer Help Center* 📚\n\n"
                "*Here's what I can work with:*\n"
                "• 📄 *PDF Files* - Perfect for textbooks and articles\n"
                "• 📝 *Word Documents* (.docx) - Great for study materials\n"
                "• 📃 *Text Files* (.txt) - Simple and effective\n"
                "• 🔗 *Web URLs* - Share any article or webpage\n"
                "• 💬 *Text Messages* - Type or paste any content\n"
                "*Quick Commands:*\n"
                "• /start - 🏁 Restart your learning journey\n"
                "• /settings - ⚙️ Customize your experience\n"
                "@SimpleLearn\\_main\\_admin - 📞 Contact support\n\n",
"send_document": "📤 <b>Ready to Create Your Quiz!</b>\n\n<b>Please share any of the following:</b>\n• 📄 A document\n• 🔗 A URL\n• 💭 Some text\n\n<b>I'll transform it into an engaging quiz for you!</b> 🎯",
"processing": "⏳ *I'm already processing your previous file...*\n\n*Please wait until it's finished before sending more.*\n\nIf you want to start over, send /start.",        "generating_quiz": "🧠 *Creating Your Custom Quiz...*\n\n*I'm crafting engaging questions to test your knowledge.*\n*Almost there!* ⚡",
        "error": "❌ *Oops! Something Went Wrong*\n\n*I couldn't process your request at this time.*\n*Please try again or share a different document.*",
        "language": "🌐 Language Settings",
        "quiz_type": "📝 Quiz Format",
        "settings": "⚙️ *Customize Your Experience*",
        "current_language": "🔤 *Your current language:* ",
        "current_quiz_type": "📝 *Your current quiz format:* ",
        "too_large": "⚠️ *File Size Limit Exceeded*\n\n*The document exceeds our 15MB limit.*\n*Please share a smaller file or split the content.*",
        "unsupported": "⚠️ *Unsupported Format*\n\n*I can work with:*\n• 📄 PDF files\n• 📝 DOCX files\n• 📃 TXT files\n• 🔗 URLs\n• 💭 Text messages",
        "transcribing": "🎤 *Transcribing Your Audio...*\n\n*I'm carefully converting your audio to text.*\n*This might take a moment.*",
        "processing_video": "🎥 *Processing Your Video...*\n\n*I'm extracting the audio and converting it to text.*\n*This may take a few minutes depending on the length.*",
        "no_api_key": "⚠️ *Audio/Video Processing Unavailable*\n\n*The transcription service is currently unavailable.*\n*Please contact the bot administrator for assistance.*",
    "premium": "✨ *Premium Quiz Features* ✨\n\n"
               "*Enhance your learning experience with:*\n"
               "• 📝 Customizable question count (3-10)\n"
               "• ⏱️ Flexible quiz timing (15-120 seconds)\n" 
               "• ⚡️ Priority quiz generation\n\n"
               "💎 *Only 30 000 UZS/month*\n"
               "👉 /upgrade to upgrade",
 "quiz_ready": "✅ *Quiz Ready!*\n\n"
                     "*{title}*\n\n"
                     "*Summary:* {summary}\n\n"
                     "⏱️ *Time limit:* {quiz_time} seconds per question\n"
                     "📝 *Number of questions:* {num_questions}\n\n"
                     "🎮 *Choose an option:*\n"
                     "🎯 *Start the quiz* to test your knowledge\n"
                     "📤 *Share the quiz* with friends or groups",
            "content_too_short": "⚠️ *Content too short*\n\nThe extracted content is too short to create a meaningful summary. Please provide more content.",
        "quiz_title": "📝 Multiple Choice Quiz",
        "quiz_questions": "📝 Quiz Questions",
        "options": "Options",
        "answer": "Answer",
        "quiz_completed": (
            "📊 *Quiz Completed!*\n\n"
            "*Your Results:*\n"
            "Total Questions: {total_questions}\n"
            "Correct Answers: {correct_answers}\n"
            "Accuracy: {accuracy:.1f}%\n"
            "Time Spent: {time_spent:.1f} seconds\n\n"
            "Would you like to create another quiz? Start with /start"
        ),
        "content_extracted": "Content Successfully Extracted",
        "preview": "Preview",
        "choose_num_questions": "How many questions would you like in your quiz?",
        "confirm_num_questions": "Great! Your quiz will have {num_questions} questions.\n\nPress the button below to generate your quiz.",

       # Balance messages
        "balance": "💰 Balance",
        "balance_info": """💰 *Your Balance*
*Current Balance:* {balance:,} UZS
*Quiz Available:* {presentations_possible}
*Friends Invited:* {invited_count}

*Quiz Generation Cost:* 2,000 UZS per quiz
*Earn 2,000 UZS for each friend you invite.*""",
        
        # Share messages
        "share": "🔗 Share & Earn",
        "share_earn": "🔗 Share & Earn",
        "share_message": """🔗 *Share & Earn 1 free quiz for each friend*

*Your Referral Link:*
`{referral_link}`

*How it works:*
• Share your unique link with friends
• When they join using your link, you get 1 free quiz
• No limit on referrals

*Your Statistics:*
• Friends invited: {invited_count}
• Total earned: {invited_count} x 2,000 = {earned_amount:,} UZS""",
        
        "share_telegram": "📱 Share on Telegram",
        "share_text": "🎉 Creating amazing quizzes has never been this easy!\n🪄 Convert text, documents, audio or video into professional PowerPoint slides in just seconds!\n📎 No complexity - just upload and it's ready!\n👫 For every friend who joins through your link - 1 quizFREE!\n📈 Unlimited invites - more friends, more opportunities!\n🚀 Join me and start for free right now: 👉",

        "copy_link": "📋 Copy Link",
        "link_copied": "✅ Link copied. Share it with your friends to earn 2,000 UZS for each referral.",
        "back_to_menu": "🔙 Back to Menu",
        "topup_button": "💳 Top Up Balance",



        # Share messages
        "share": "🔗 Share & Earn",
        "share_earn": "🔗 Share & Earn",
        "share_message": """🔗 *Share & Earn 1 free quiz for each friend*

*Your Referral Link:*
`{referral_link}`

*How it works:*
• Share your unique link with friends
• When they join using your link, you get 1 free quiz
• No limit on referrals

*Your Statistics:*
• Friends invited: {invited_count}
• Total earned: {invited_count} x 2,000 = {earned_amount:,} UZS""",
        
        "share_telegram": "📱 Share on Telegram",
        "share_text": "🎉 Creating amazing quizzes has never been this easy!\n🪄 Convert text, documents, audio or video into professional PowerPoint slides in just seconds!\n📎 No complexity - just upload and it's ready!\n👫 For every friend who joins through your link - 1 quizFREE!\n📈 Unlimited invites - more friends, more opportunities!\n🚀 Join me and start for free right now: 👉",

        "copy_link": "📋 Copy Link",
        "link_copied": "✅ Link copied. Share it with your friends to earn 2,000 UZS for each referral.",
        "back_to_menu": "🔙 Back to Menu",
        "topup_button": "💳 Top Up Balance",
        
        # Welcome messages
        "welcome_with_referral": """🎉 *Welcome {name}.*

Thanks for joining through a friend's referral. You're all set to start creating amazing quizzes.

Your friend will receive 2,000 UZS as a bonus for inviting you.""",


        # Other messages
        "premium_active": "✅ Premium Active",
        "premium_inactive": "❌ Premium Inactive",
        "create_presentation": "🎯 Create Presentation",
        
        "topup_button": "💳 Top Up Balance",
        "topup_title": "Balance Top-up",
        "topup_description": "Add {amount:,} UZS to your balance",
        
         "select_topup_amount": (
            "💳 Select top-up amount:\n\n"
            "Funds will be automatically added to your balance. Keep in mind (only after 10th quizzes): \n\n"
            "• Up to 20 questions: 2,000 UZS per quiz\n\n"
            "• Up to 30 questions: 3,000 UZS per quiz"
        ),
        
        "custom_amount": "✏️ Enter Custom Amount",
        "cancel": "❌ Cancel",
        "currency": "UZS",
        
        "enter_custom_amount": """
✏️ *Enter Custom Amount*

Please enter the amount you want to add to your balance (minimum 1,000 UZS, maximum 100,000 UZS):
        """,
        
        "amount_too_low": "❌ Amount too low. Minimum top-up is 1,000 UZS.",
        "amount_too_high": "❌ Amount too high. Maximum top-up is 100,000 UZS.",
        "invalid_amount": "❌ Invalid amount. Please enter a valid number.",
                "topup_balance": "💳 Top Up Balance",

        "balance_topup_success": """
✅ *Balance Top-up Successful.*

*Added:* {amount:,.0f} UZS
*New Balance:* {new_balance:,.0f} UZS

Your balance has been updated.
        """,
        
        "insufficient_balance": """
❌ *Insufficient Balance*

*Current Balance:* {current_balance:,} UZS
*Required:* {required:,} UZS

Please top up your balance to continue.
        """,
        
        "topup_cancelled": "❌ Balance top-up cancelled.",
        
        # Status messages
        "premium_active": "✅ Premium Active",
        
        # Error messages
        "payment_error": "❌ Payment error. Please try again later.",
        "payment_provider_error": "❌ Payment provider error. Please try again later.",
        "payment_processing_error": "❌ Error processing payment. Please contact support.",


                # Referral messages
        "referral_bonus_notification": "🎉 *Referral Bonus!*\n\nYou received *2,000 UZS* for inviting a friend. Thank you for sharing!",
        "already_using_bot": "ℹ️ You are already using this bot. Welcome back!",
        "continue_to_menu": "Continue to Menu",
        

"try_again": "🔄 Try Again. Start the bot with /start",
"split_quiz_button": "📂 Split Quiz",
        "quiz_ready_title": "Quiz Ready!",
        "summary_label": "Summary",
        "time_limit": "Time limit",
        "seconds_per_question": "seconds per question",
        "num_questions": "Number of questions",
        "choose_option": "Choose an option",
        "start_quiz_desc": "Start the quiz to test your knowledge",
        "share_quiz_desc": "Share the quiz with friends or groups",











    },
    "ru": {
            "welcome": "🌟 *Добро пожаловать в SimpleQuizzer!* 🌟\n\n📚 *Я помогу вам учиться через интерактивные тесты!* ✨\n\n *Наш новый бот генерирует презентации для Вас: @SimplePresentation_maker_bot*",
        "choose_language": "🌍 *Давайте начнем!*\n\n*Пожалуйста, выберите предпочитаемый язык:*",
     "language_selected": "✅ *Отлично! Русский язык установлен!*\n\n*Вы готовы начать обучение с SimpleQuizzer!* Начните бот с /start  🚀",
        "help": "📚 *Центр помощи SimpleQuizzer* 📚\n\n"
                "*Вот с чем я могу работать:*\n"
                "• 📄 *PDF файлы* - Идеально для учебников и статей\n"
                "• 📝 *Word документы* (.docx) - Отлично для учебных материалов\n"
                "• 📃 *Текстовые файлы* (.txt) - Просто и эффективно\n"
                "• 🔗 *Веб-ссылки* - Поделитесь любой статьей или веб-страницей\n"
                "• 💬 *Текстовые сообщения* - Введите или вставьте любой контент\n"
                "*Быстрые команды:*\n"
                "• /start - 🏁 Перезапустить обучение\n"
                "• /settings - ⚙️ Настроить опыт\n"
                "• @SimpleLearn\\_main\\_admin - 📞 Связаться с поддержкой\n\n",
"send_document": "📤 <b>Готов создать ваш тест!</b>\n\n<b>Пожалуйста, поделитесь:</b>\n• 📄 Документом\n• 🔗 Ссылкой\n• 💭 Текстом\n\n<b>Я превращу это в увлекательный тест!</b> 🎯",
"processing": "⏳ *Я уже обрабатываю ваш предыдущий файл...*\n\n*Пожалуйста, дождитесь завершения, прежде чем отправлять новые материалы.*\n\nЕсли хотите начать сначала, отправьте /start.",        "generating_quiz": "🧠 *Создание вашего теста...*\n\n*Я составляю интересные вопросы для проверки знаний.*\n*Почти готово!* ⚡",
        "error": "❌ *Упс! Что-то пошло не так*\n\n*Не удалось обработать ваш запрос.*\n*Пожалуйста, попробуйте снова или поделитесь другим документом.*",
        "language": "🌐 Настройки языка",
        "quiz_type": "📝 Формат теста",
        "settings": "⚙️ *Настройте свой опыт*",
        "current_language": "🔤 *Ваш текущий язык:* ",
        "current_quiz_type": "📝 *Ваш текущий формат теста:* ",
        "too_large": "⚠️ *Превышен размер файла*\n\n*Документ превышает лимит в 15МБ.*\n*Пожалуйста, поделитесь файлом меньшего размера или разделите контент.*",
        "unsupported": "⚠️ *Неподдерживаемый формат*\n\n*Я могу работать с:*\n• 📄 PDF файлами\n• 📝 DOCX файлами\n• 📃 TXT файлами\n• 🔗 Ссылками\n• 💭 Текстовыми сообщениями",
        "transcribing": "🎤 *Транскрибирование вашего аудио...*\n\n*Я тщательно преобразую аудио в текст.*\n*Это может занять некоторое время.*",
        "processing_video": "🎥 *Обработка вашего видео...*\n\n*Я извлекаю аудио и преобразую его в текст.*\n*Это может занять несколько минут в зависимости от длины.*",
        "no_api_key": "⚠️ *Обработка аудио/видео недоступна*\n\n*Служба транскрипции в настоящее время недоступна.*\n*Пожалуйста, свяжитесь с администратором бота.*",
        "premium": "✨ *Премиум функции тестов* ✨\n\n"
               "*Улучшите свой опыт обучения:*\n"
               "• 📝 Настраиваемое количество вопросов (3-10)\n"
               "• ⏱️ Гибкое время теста (15-120 секунд)\n"
               "• ⚡️ Приоритетная генерация\n\n"
               "💎 *Всего 300 UZS/месяц*\n"
               "👉 /upgrade для подключения",
       "quiz_ready": "✅ *Тест готов!*\n\n"
                     "*{title}*\n\n"
                     "*Краткое содержание:* {summary}\n\n"
                     "⏱️ *Лимит времени:* {quiz_time} секунд на вопрос\n"
                     "📝 *Количество вопросов:* {num_questions}\n\n"
                     "🎮 *Выберите действие:*\n"
                     "🎯 *Начать тест* чтобы проверить свои знания\n"
                     "📤 *Поделиться тестом* с друзьями или группами",
            "content_too_short": "⚠️ *Слишком короткий текст*\n\nИзвлеченный контент слишком короткий для создания осмысленного обзора. Пожалуйста, предоставьте больше контента.",
        "quiz_title": "📝 Тест с вариантами ответов",
        "quiz_questions": "📝 Вопросы теста",
        "options": "Варианты",
        "answer": "Ответ",
                "quiz_completed": (
            "📊 *Тест завершен!*\n\n"
            "*Ваши результаты:*\n"
            "Всего вопросов: {total_questions}\n"
            "Правильных ответов: {correct_answers}\n"
            "Точность: {accuracy:.1f}%\n"
            "Время: {time_spent:.1f} секунд\n\n"
            "Хотите создать еще один тест? Начните с /start"
        ),
        "content_extracted": "Контент успешно извлечён",
        "preview": "Превью",
        "choose_num_questions": "Сколько вопросов вы хотите в вашем тесте?",
        "confirm_num_questions": "Отлично! В вашем тесте будет {num_questions} вопросов.\n\nНажмите кнопку ниже, чтобы создать тест.",
 
    
 
        # Balance messages

         "balance": "💰 Баланс",
        "balance_info": """💰 *Ваш Баланс*

*Текущий баланс:* {balance:,} UZS
*Доступно презентаций:* {presentations_possible}
*Приглашено друзей:* {invited_count}

*Стоимость создания Quiz:* 2,000 UZS за квиза
*Зарабатывайте 3,000 UZS за каждого приглашенного друга.*""",




        # Share messages
        "share": "🔗 Поделиться и заработать",
        "share_earn": "🔗 Поделиться и заработать",
        "share_message": """🔗 *Поделитесь и заработайте 2,000 UZS*

*Ваша реферальная ссылка:*
`{referral_link}`

*Как это работает:*
• Поделитесь уникальной ссылкой с друзьями
• Когда они присоединятся по вашей ссылке, вы получите 2,000 UZS
• Нет ограничений на количество рефералов.

*Ваша статистика:*
• Приглашено друзей: {invited_count}
• Всего заработано: {invited_count} x 2,000 = {earned_amount:,} UZS""",
        
        "share_telegram": "📱 Поделиться в Telegram",
        "share_text": "🎉 Создание потрясающих презентаций никогда не было таким простым!\n🪄 Превратите текст, документы, аудио или видео в профессиональные слайды PowerPoint за считанные секунды!\n📎 Никаких сложностей - просто загрузите и всё готово!\n👫 За каждого друга, присоединившегося по вашей ссылке - 1 викторина БЕСПЛАТНО!\n📈 Неограниченные приглашения - больше друзей, больше возможностей!\n🚀 Присоединяйтесь ко мне и начните бесплатно прямо сейчас: 👉",

         "copy_link": "📋 Копировать ссылку",
        "link_copied": "✅ Ссылка скопирована. Поделитесь ею с друзьями, чтобы заработать 2,000 UZS за каждого реферала.",
        "back_to_menu": "🔙 Назад в меню",
        "topup_button": "💳 Пополнить баланс",
        
        # Welcome messages
        "welcome_with_referral": """🎉 *Добро пожаловать {name}.*

Спасибо за присоединение по реферальной ссылке друга. Теперь вы готовы создавать потрясающие викторины.

Ваш друг получит 2,000 UZS в качестве бонуса за приглашение.""",
        
        # Other messages
        "premium_active": "✅ Премиум активен",
        "premium_inactive": "❌ Премиум неактивен",
        "create_presentation": "🎯 Создать викторины",
        
        "topup_button": "💳 Пополнить баланс",
        "topup_title": "Пополнение баланса",
        "topup_description": "Добавить {amount:,} сум на ваш баланс",
        
        "select_topup_amount": (
            "💳 Выберите сумму пополнения:\n\n"
            "Средства будут автоматически зачислены на ваш баланс. После 10 ого квиза цены такие, но до 10 квиззов это совершенно бесплатно!\n"
            "• До 20 вопросов: 2 000 сум за викторину\n"
            "• До 30 вопросов: 3 000 сум за викторину"
        ),
        
        "custom_amount": "✏️ Ввести свою сумму",
        "cancel": "❌ Отмена",
        "currency": "сум",
        
        "enter_custom_amount": """
✏️ *Введите свою сумму*

Пожалуйста, введите сумму, которую хотите добавить на баланс (минимум 1,000 сум, максимум 100,000 сум):
        """,
        
        "amount_too_low": "❌ Сумма слишком мала. Минимальное пополнение 1,000 сум.",
        "amount_too_high": "❌ Сумма слишком велика. Максимальное пополнение 100,000 сум.",
        "invalid_amount": "❌ Неверная сумма. Пожалуйста, введите правильное число.",
        
        "balance_topup_success": """
✅ *Баланс успешно пополнен.*

*Добавлено:* {amount:,.0f} сум
*Новый баланс:* {new_balance:,.0f} сум

Ваш баланс обновлен.
        """,
        
        "insufficient_balance": """
❌ *Недостаточно средств*

*Текущий баланс:* {current_balance:,} сум
*Необходимо:* {required:,} сум

Пожалуйста, пополните баланс для продолжения.
        """,
        
        "topup_cancelled": "❌ Пополнение баланса отменено.",
                "topup_balance": "💳 Пополнить баланс",

        # Status messages
        "premium_active": "✅ Premium активен",
        "premium_inactive": "❌ Обычный пользователь",
        
        # Error messages
        "payment_error": "❌ Ошибка платежа. Попробуйте позже.",
        "payment_provider_error": "❌ Ошибка провайдера платежей. Попробуйте позже.",
        "payment_processing_error": "❌ Ошибка обработки платежа. Обратитесь в поддержку.",

      # Referral messages
        "referral_bonus_notification": "🎉 *Бонус за приглашение!*\n\nВы получили *2,000 UZS* за приглашение друга. Спасибо за то, что делитесь!",
        "already_using_bot": "ℹ️ Вы уже используете этого бота. Добро пожаловать обратно!",
        "continue_to_menu": "Перейти в меню",


       "slides": "Слайды",
        "title": "Название",
        "style": "Стиль",
        "summary": "Краткое описание",
        "generated_by": "🤖 Создано с помощью @SimplePresentation_maker_bot",
"document_processing_error": "❌ Ошибка обработки документа. Убедитесь, что это допустимый формат (PDF, DOCX, TXT) и попробуйте снова.",

"try_again": "🔄 Попробовать снова. Запустите бота с помощью /start",
        "split_quiz_button": "📂 Разделить Квиз",
        
        
        "quiz_ready_title": "Квиз готов!",
        "summary_label": "Краткое содержание",
        "time_limit": "Ограничение времени",
        "seconds_per_question": "секунд на каждый вопрос",
        "num_questions": "Количество вопросов",
        "choose_option": "Выберите опцию",
        "start_quiz_desc": "Начать викторину, чтобы проверить свои знания",
        "share_quiz_desc": "Поделиться викториной с друзьями или группами",










    
    },
    "uz": {
"welcome": "🌟 *SimpleQuizzer'ga xush kelibsiz!* 🌟\n\n"
            "📚 *Men sizga interaktiv testlar orqali o'rganishda yordam beraman!* ✨\n\n"
            "*Menga oddiygina mavzuni yuboring*\n"
            "*Men uni bilimingizni tekshirish uchun qiziqarli testlarga aylantiraman!* 🎯 \n\n "
            "*Bizning yangi botimiz siz uchun sekundlarda maxsus presentatsiyalar yaratib beradi: @SimplePresentation_maker_bot*",
        "choose_language": "🌍 *Keling, boshlaymiz!*\n\n*Iltimos, o'zingizga qulay tilni tanlang:*",

       "language_selected": "✅ *Ajoyib! O'zbek tili o'rnatildi!*\n\n*Siz SimpleQuizzer bilan Quiz tuzishga tayyorsiz! /start bilan botni boshlab oling* 🚀",
        "help": "📚 *SimpleQuizzer Yordam Markazi* 📚\n\n"
                "*Men quyidagilar bilan ishlay olaman:*\n"
                "• 📄 *PDF fayllar* - Darsliklar va maqolalar uchun ideal\n"
                "• 📝 *Word hujjatlar* (.docx) - O'quv materiallari uchun ajoyib\n"
                "• 📃 *Matn fayllar* (.txt) - Oddiy va samarali\n"
                "• 🔗 *Veb-havolalar* - Har qanday maqola yoki veb-sahifani ulashing\n"
                "• 💬 *Matn xabarlar* - Har qanday kontentni kiriting yoki joylang\n"
                "*Tezkor buyruqlar:*\n"
                "• /start - 🏁 O'rganishni qayta boshlash\n"
                "• /settings - ⚙️ Tajribani sozlash\n"
                "• @SimpleLearn\\_main\\_admin - 📞 Admin bilan bog'lanish\n\n",
                "send_document": "📤 <b>Testingizni yaratishga tayyorman!</b>\n\n<b>Iltimos, quyidagilardan birini ulashing:</b>\n• 📄 Hujjat\n• 🔗 Havola\n• 💭 Matn\n\n<b>Men uni qiziqarli quizga aylantiraman!</b> 🎯",
"processing": "⏳ *Faylingiz hali qayta ishlanmoqda...*\n\n*Iltimos, tugaguncha kuting va yangi fayl yubormang.*\n\nYangi boshlash uchun /start buyrug'ini yuboring.",        "generating_quiz": "🧠 *Testingiz yaratilmoqda...*\n\n*Men bilimingizni tekshirish uchun qiziqarli savollar tuzmoqdaman.*\n*Deyarli tayyor!* ⚡",
        "error": "❌ *Voy! Nimadir xato ketdi*\n\n*So'rovingizni qayta ishlay olmadim.*\n*Iltimos, qayta urinib ko'ring yoki boshqa hujjat yuboring.*",
        "language": "🌐 Til sozlamalari",
        "quiz_type": "📝 Test formati",
        "settings": "⚙️ *Tajribangizni sozlash*",
        "current_language": "🔤 *Joriy tilingiz:* ",
        "current_quiz_type": "📝 *Joriy test formatingiz:* ",
        "too_large": "⚠️ *Fayl hajmi chegarasidan oshib ketdi*\n\n*Hujjat 15MB chegarasidan oshib ketdi.*\n*Iltimos, kichikroq fayl yuboring yoki kontentni bo'ling.*",
        "unsupported": "⚠️ *Qo'llab-quvvatlanmaydigan format*\n\n*Men quyidagilar bilan ishlay olaman:*\n• 📄 PDF fayllar\n• 📝 DOCX fayllar\n• 📃 TXT fayllar\n• 🔗 Havolalar\n• 💭 Matn xabarlar",
        "transcribing": "🎤 *Audioingiz transkripsiya qilinmoqda...*\n\n*Men audioni matnga diqqat bilan aylantirayapman.*\n*Bu biroz vaqt olishi mumkin.*",
        "processing_video": "🎥 *Videongiz qayta ishlanmoqda...*\n\n*Men audioni ajratib olish va matnga aylantirish jarayonida.*\n*Video uzunligiga qarab bir necha daqiqa vaqt olishi mumkin.*",
        "no_api_key": "⚠️ *Audio/video qayta ishlash mavjud emas*\n\n*Transkripsiya xizmati hozirda mavjud emas.*\n*Iltimos, bot administratoriga murojaat qiling.*",
    "premium": "✨ *Premium Test Xususiyatlari* ✨\n\n"
               "*Yanada osonroq o'rganing:*\n"
               "• 📝 Savollar sonini sozlash (3-10)\n"
               "• ⏱️ Moslashuvchan test vaqti (15-120 soniya)\n"
               "• ⚡️ 2x fayl hajmi\n\n"
               "💎 *Atigi 30,000 so'm/oyiga*\n"
               "👉 /upgrade orqali ulaning",
"quiz_ready": "✅ *Quiz tayyor!*\n\n"
                     "*{title}*\n\n"
                     "*Qisqacha mazmuni:* {summary}\n\n"
                     "⏱️ *Vaqt chegarasi:* har bir savol uchun {quiz_time} soniya\n"
                     "📝 *Savollar soni:* {num_questions}\n\n"
                     "🎮 *Tanlang:*\n"
                     "🎯 *Testni boshlash* bilimingizni tekshirish uchun\n"
                     "📤 *Testni ulashish* do'stlar yoki guruhlar bilan",
           "content_too_short": "⚠️ *Kontent juda qisqa*\n\nAjratib olingan kontent mazmunli test tuzish uchun juda qisqa. Iltimos, ko'proq ma'lumot taqdim eting. Minimum 50 so'z",
        "quiz_title": "📝 Ko'p tanlovli test",
        "quiz_questions": "📝 Test savollari",
        "options": "Variantlar",
        "answer": "Javob",
        "quiz_completed": (
            "📊 *Test yakunlandi!*\n\n"
            "*Natijalaringiz:*\n"
            "• *Jami savollar:* `{total_questions}`\n"
            "• *To'g'ri javoblar:* `{correct_answers}`\n"
            "• *Aniqlik:* `{accuracy:.1f}%`\n"
            "• *Sarflangan vaqt:* `{time_spent:.1f} soniya`\n\n"
            "Yana bir test yaratishni xohlaysizmi? /start bilan boshlang"
        ),
         "content_extracted": "Mavzu muvaffaqiyatli ajratib olindi",
        "preview": "Ko‘rinish",
        "choose_num_questions": "*Testda nechta savol bo‘lishini xohlaysiz?*",
        "confirm_num_questions": "*Ajoyib! Testda {num_questions} ta savol bo‘ladi.\n\nTestni yaratish uchun quyidagi tugmani bosing.*",
  

        # Balance messages
        "balance": "💰 Balans",
        "balance_info": """💰 *Sizning Balans*

*Joriy balans:* {balance:,} UZS
*Shuncha quiz yarata olasiz:* {presentations_possible}
*Taklif qilingan do'stlar:* {invited_count}

*Quiz yaratish narxi:* Har bir quiz uchun 3,000 UZS
*Har bir do'stingiz uchun 2,000 UZS ishlang.*""",


        "select_topup_amount": (
            "💳 To'lov miqdorini tanlang:\n\n"
            "Pul mablag'lari avtomatik tarzda balansingizga qo'shiladi. Quizlar 10 tagacha mutlaqo BEPUL, lekin undan keyin narxlar quyidagicha: \n\n"
            "• 20 ta savolgacha: har bir viktorina uchun 2 000 so'm\n\n"
            "• 30 ta savolgacha: har bir viktorina uchun 3 000 so'm\n"
        ),



        # Share messages
        "share": "🔗 Bepul quiz olish",
        "share_earn": "🔗 Ulashing va bepul quiz",
"share_message": """🔗 *Ulashing va bepul quiz yarating*

*Sizning referral havolangiz:*
{referral_link}

*Qanday ishlaydi:*
- Ushbu havolangizni do'stlaringiz bilan ulashing
- Ular sizning havolangiz orqali qo'shilganda, siz bepul quiz yarata olasiz.
- Referallar soniga cheklov yo'q.

*Sizning statistikangiz:*
- Taklif qilingan do'stlar: {invited_count}
- Jami ishlangan: {earned_amount} UZS""",
        
        "share_telegram": "📱 Telegramda ulashing",
        "share_text": "🎉 Ajoyib quizlar yaratish hech qachon bu qadar oson bo'lmagan!\n🪄 Matn, hujjat, audio yoki videoni atigi bir necha soniyada professional PowerPoint slaydlarga aylantiring!\n📎 Hech qanday murakkablik yo'q - faqat yuklang va tayyor!\n👫 Har bir do'stingiz sizning havolangiz orqali qo'shilsa - 1 ta quiz BEPUL!\n📈 Takliflar cheklanmagan - ko'proq do'st, ko'proq imkoniyatlar!\n🚀 Men bilan qo'shiling va hoziroq bepul boshlang: 👉",
            "copy_link": "📋 Havolani nusxalash",
        "link_copied": "✅ Havola nusxalandi. Har bir referal uchun 2,000 UZS ishlab olish uchun do'stlaringiz bilan ulashing.",
        "back_to_menu": "🔙 Menyuga qaytish",
        "topup_button": "💳 Balansni to'ldirish",


        # Referral messages
       "referral_bonus_notification": "🎉 *Referral bonusi!*\n\nDo'stingizni taklif qilganingiz uchun *2,000 UZS* oldingiz. Ulashganingiz uchun rahmat!",
        "already_using_bot": "ℹ️ Siz allaqachon ushbu botdan foydalanmoqdasiz. Qaytganingiz bilan!",
        "continue_to_menu": "Menyuga o'tish",
  


        # Welcome messages
        "welcome_with_referral": """🎉 *Xush kelibsiz {name}.*

Do'stingizning referral havolasi orqali qo'shilganingiz uchun rahmat. Endi ajoyib quizlar yaratishga tayyorsiz.

Do'stingiz sizni taklif qilgani uchun 2,000 UZS bonus oladi.""",
        
       # Other messages
        "premium_active": "✅ Premium faol",
        "premium_inactive": "❌ Premium faol emas",
        "create_presentation": "🎯 Taqdimot yaratish",
        
        "topup_button": "💳 Balansni to'ldirish",
        "topup_title": "Balansni to'ldirish",
        "topup_description": "Balansga {amount:,} so'm qo'shish",
        "topup_balance": "💳 Balansni to‘ldirish",

        
        "select_amount": """
💳 *To'ldirish miqdorini tanlang*

Balansga qancha qo'shmoqchi ekanligingizni tanlang:
        """,
        
        "custom_amount": "✏️ O'z miqdorini kiriting",
        "cancel": "❌ Bekor qilish",
        "currency": "so'm",
        
        "enter_custom_amount": """
✏️ *O'z miqdorini kiriting*

Balansga qo'shmoqchi bo'lgan miqdorni kiriting (minimum 1,000 so'm, maksimum 100,000 so'm):
        """,
        
        "amount_too_low": "❌ Miqdor juda kam. Minimum to'ldirish 1,000 so'm.",
        "amount_too_high": "❌ Miqdor juda ko'p. Maksimum to'ldirish 100,000 so'm.",
        "invalid_amount": "❌ Noto'g'ri miqdor. Iltimos, to'g'ri raqam kiriting.",
        
        "balance_topup_success": """
✅ *Balans muvaffaqiyatli to'ldirildi.*

*Qo'shildi:* {amount:,.0f} so'm
*Yangi balans:* {new_balance:,.0f} so'm

Balansngiz yangilandi.
        """,
        
        "insufficient_balance": """
❌ *Balansda mablag' yetarli emas*

*Joriy balans:* {current_balance:,} so'm
*Kerak:* {required:,} so'm

Davom etish uchun balansni to'ldiring.
        """,
        
        "topup_cancelled": "❌ Balansni to'ldirish bekor qilindi.",
        
        # Status messages
        "premium_active": "✅ Premium faol",
        "premium_inactive": "❌ Oddiy foydalanuvchi",
        
        # Error messages
        "payment_error": "❌ To'lov xatosi. Keyinroq qayta urinib ko'ring.",
        "payment_provider_error": "❌ To'lov provayderi xatosi. Keyinroq qayta urinib ko'ring.",
        "payment_processing_error": "❌ To'lovni qayta ishlashda xatolik. Qo'llab-quvvatlash bilan bog'laning.",


        "slides": "Slaydlar",
        "title": "Sarlavha",
        "style": "Uslub",
        "summary": "Qisqacha mazmuni",
        "generated_by": "🤖 @SimplePresentation_maker_bot tomonidan yaratilgan",

"document_processing_error": "❌ Hujjatni qayta ishlashda xatolik yuz berdi. Iltimos, boshqa hujjat yuboring yoki qo'llab-quvvatlash xizmatiga murojaat qiling.",

"try_again": "🔄 Qayta urinib ko'ring. /start bilan botni ishga tushiring",
"split_quiz_button": "📂 Tayyor quizni bo'lish",

        "quiz_ready_title": "Quiz tayyor!",
        "summary_label": "Qisqacha mazmuni",
        "time_limit": "Vaqt chegarasi",
        "seconds_per_question": "soniya har bir savol uchun",
        "num_questions": "Savollar soni",
        "choose_option": "Tanlang",
        "start_quiz_desc": "Testni boshlash bilimingizni tekshirish uchun",
        "share_quiz_desc": "Testni ulashish do'stlar yoki guruhlar bilan",









    }
}


REFERRAL_TRANSLATIONS = {
    "en": {
        "referral_bonus_notification": "🎉 *Referral Bonus!*\n\nGreat news! Someone joined using your referral link and you received *3 000 UZS*!\n\nKeep sharing to earn more free quizzes! 🚀",
        "welcome_with_referral": "🎉 *Welcome {name}!*\n\nYou joined through a friend's referral link! Your friend will receive *3 000 UZS* as a bonus for inviting you.\n\n💡 *Pro tip:* Share your own referral link below to earn free quiz when your friends join!\n\n🔗 *Your referral link:*\n`{referral_link}`\n\n📈 *How it works:*\n• Share your link with friends\n• They join the bot using your link\n• You get 1 free quizfor each friend\n• No limits on referrals!",
        "share_your_link": "🔗 Share Your Link",
        "continue_to_menu": "📱 Continue to Menu"
    },
    "ru": {
        "referral_bonus_notification": "🎉 *Реферальный бонус!*\n\nОтличные новости! Кто-то присоединился по вашей реферальной ссылке и вы получили *3 000 UZS*!\n\nПродолжайте делиться, чтобы заработать больше бесплатных викторин! 🚀",
        "welcome_with_referral": "🎉 *Добро пожаловать, {name}!*\n\nВы присоединились по реферальной ссылке друга! Ваш друг получит *3 000 UZS* в качестве бонуса за приглашение.\n\n💡 *Совет:* Поделитесь своей реферальной ссылкой ниже, чтобы заработать бесплатные викторины, когда ваши друзья присоединятся!\n\n🔗 *Ваша реферальная ссылка:*\n`{referral_link}`\n\n📈 *Как это работает:*\n• Поделитесь ссылкой с друзьями\n• Они присоединяются к боту по вашей ссылке\n• Вы получаете 1 бесплатную викторину за каждого друга\n• Без ограничений на рефералы!",
        "share_your_link": "🔗 Поделиться ссылкой",
        "continue_to_menu": "📱 Перейти в меню"
    },
    "uz": {
        "referral_bonus_notification": "🎉 *Referal bonusi!*\n\nZo'r yangilik! Kimdir sizning referal havolangiz orqali qo'shildi va siz *3 000 UZS* oldingiz!\n\nKo'proq bepul quizlar olish uchun ulashishni davom eting! 🚀",
        "welcome_with_referral": "🎉 *Xush kelibsiz, {name}!*\n\nSiz do'stingizning referal havolasi orqali qo'shildingiz! Sizni taklif qilgani uchun do'stingiz *3 000 UZS* bonus sifatida oladi.\n\n💡 *Maslahat:* Do'stlaringiz qo'shilganda bepul quizlar olish uchun pastdagi referal havolangizni ulashing!\n\n🔗 *Sizning referal havolangiz:*\n`{referral_link}`\n\n📈 *Qanday ishlaydi:*\n• Havolangizni do'stlaringiz bilan ulashing\n• Ular sizning havolangiz orqali botga qo'shiladi\n• Har bir do'st uchun 1 ta bepul quiz olasiz\n• Referallarga cheklov yo'q!",
        "share_your_link": "🔗 Havolani ulashish",
        "continue_to_menu": "📱 Menyuga o'tish"
    }
}




QUIZ_TYPE_INFO = {
    "en": (
        "*Please select your preferred quiz type:*\n\n"
        "1️⃣ *Multiple Choice*\n"
        "• Questions with multiple options\n"
        "• One correct answer\n"
        "• Interactive polls\n"
        "• Immediate feedback\n\n"
        "2️⃣ *Open Ended*\n"
        "• Questions with text answers\n"
        "• More detailed responses\n"
        "• Self-paced learning\n"
        "• Great for complex topics\n\n"
        "🔄 You can change this later in /settings"
    ),
    "ru": (
        "*Пожалуйста, выберите предпочтительный тип викторины:*\n\n"
        "1️⃣ *Множественный выбор*\n"
        "• Вопросы с вариантами ответов\n"
        "• Один правильный ответ\n"
        "• Интерактивные опросы\n"
        "• Мгновенная обратная связь\n\n"
        "2️⃣ *Открытые вопросы*\n"
        "• Вопросы с текстовыми ответами\n"
        "• Более подробные ответы\n"
        "• Обучение в своем темпе\n"
        "• Отлично подходит для сложных тем\n\n"
        "🔄 Вы можете изменить это позже в /settings"
    ),
    "uz": (
        "*Iltimos, o'zingizga mos viktorina turini tanlang:*\n\n"
        "1️⃣ *Quiz savollar*\n"
        "• 4 xil javob variantlari bilan savollar (quiz shaklida)\n"
        "• Interaktiv so'rovlar\n"
        "• Tezkor natijalar\n\n"
        "2️⃣ *Ochiq savollar*\n"
        "• Matnli javoblar bilan savollar\n"
        "• Batafsil javoblar\n"
        "• O'z sur'atingizda o'rganish\n"
        "• Murakkab mavzular uchun qulay\n\n"
        "🔄 Buni keyinroq /settings orqali o'zgartirishingiz mumkin"
    )
}


PREMIUM_MESSAGES = {
    "en": {
        "active": (
            "✨ *You have already activated Premium Subscription* ✨\n\n"
            "📅 *Subscription Period:*\n"
            "• Start: {start}\n"
            "• End: {end}\n\n"
            "⏳ *Time Remaining:*\n"
            "• {days} days and {hours} hours\n\n"
            "🌟 *Your Premium Features:*\n"
            "• 📝 Customizable questions (5-20 questions)\n"
            "• ⏱️ Customizable quiz time (15-120 seconds)\n"
            "• ⚡ Priority processing\n"
            "• 📊 Advanced quiz statistics\n\n"
            "💡 *Tip:* Use /settings to customize your quiz preferences"
        ),
        "upgrade": (
            "🌟 *Premium Features*\n\n"
            "✨ *Enhanced Quiz Capabilities:*\n"
            "• 📝 Customizable questions (5-20 questions)\n"
            "• ⏱️ Customizable quiz time (15-120 seconds)\n"
            "• ⚡ Priority processing\n"
            "• 📊 2x bigger files processing\n\n"
            "💎 *Subscription Details:*\n"
            "• Monthly subscription\n"
            "• Automatic renewal\n"
            "Click the button below to upgrade:"
        ),
        "success": (
            "✨ *Premium Upgrade Successful!* ✨\n\n"
            "💫 *Payment Details:*\n"
            "• Amount: {amount} UZS\n"
            "• Currency: {currency}\n\n"
            "📅 *Subscription Period:*\n"
            "• Start: {start}\n"
            "• End: {end}\n\n"
            "🌟 *Premium Features Activated:*\n"
            "• 📝 Customizable questions (5-20 questions)\n"
            "• ⏱️ Customizable quiz time (15-120 seconds)\n"
            "• ⚡ Priority processing\n"
            "• 📊 Advanced quiz statistics\n\n"
            "💡 *Tip:* Use /settings to customize your quiz preferences"
        ),
        "invoice": (
            "Premium Quiz Subscription: "
            "Custom questions (5-20), custom time (15-120s), priority processing "
            "Monthly subscription, auto-renewal."
        )
    },
    "ru": {
        "active": (
            "✨ *Премиум подписка активна* ✨\n\n"
            "📅 *Период подписки:*\n"
            "• Начало: {start}\n"
            "• Конец: {end}\n\n"
            "⏳ *Осталось времени:*\n"
            "• {days} дней и {hours} часов\n\n"
            "🌟 *Ваши премиум возможности:*\n"
            "• 📝 Настраиваемое количество вопросов (5-20)\n"
            "• ⏱️ Настраиваемое время викторины (15-120 секунд)\n"
            "• ⚡ Приоритетная обработка\n"
            "• 📊 Продвинутая статистика\n\n"
            "💡 *Совет:* Используйте /settings для настройки"
        ),
        "upgrade": (
            "🌟 *Премиум возможности*\n\n"
            "✨ *Расширенные возможности викторин:*\n"
            "• 📝 Настраиваемое количество вопросов (5-20)\n"
            "• ⏱️ Настраиваемое время викторины (15-120 секунд)\n"
            "• ⚡ Приоритетная обработка\n"
            "• 📊 Файлы в 2 раза больше\n\n"
            "💎 *Детали подписки:*\n"
            "• Месячная подписка\n"
            "• Автоматическое продление\n"
            "Нажмите кнопку ниже для апгрейда:"
        ),
        "success": (
            "✨ *У Вас уже Премиум успешно активирован!* ✨\n\n"
            "💫 *Детали оплаты:*\n"
            "• Сумма: {amount} UZS\n"
            "• Валюта: {currency}\n\n"
            "📅 *Период подписки:*\n"
            "• Начало: {start}\n"
            "• Конец: {end}\n\n"
            "🌟 *Премиум возможности активированы:*\n"
            "• 📝 Настраиваемое количество вопросов (5-20)\n"
            "• ⏱️ Настраиваемое время викторины (15-120 секунд)\n"
            "• ⚡ Приоритетная обработка\n"
            "• 📊 Продвинутая статистика\n\n"
            "💡 *Совет:* Используйте /settings для настройки"
        ),
            "invoice": (
                "Премиум подписка на викторину: "
                "Свои вопросы (5-20), время (15-120с), приоритет"
                "Месячная подписка, автообновление."
            )
    },
    "uz": {
        "active": (
            "✨ *Premium obuna Sizda faollashtirilgan* ✨\n\n"
            "📅 *Obuna muddati:*\n"
            "• Boshlanishi: {start}\n"
            "• Tugashi: {end}\n\n"
            "⏳ *Qolgan vaqt:*\n"
            "• {days} kun va {hours} soat\n\n"
            "🌟 *Premium imkoniyatlaringiz:*\n"
            "• 📝 Savollar sonini sozlash (5-20 ta)\n"
            "• ⏱️ Quiz vaqtini sozlash (15-120 soniya)\n"
            "• ⚡ Ustuvor ishlov berish\n"
            "• 📊 Kengaytirilgan statistika\n\n"
            "💡 *Maslahat:* /settings orqali sozlang"
        ),
        "upgrade": (
            "🌟 *Premium imkoniyatlar*\n\n"
            "✨ *Kengaytirilgan viktorina imkoniyatlari:*\n"
            "• 📝 Savollar sonini sozlash (5-20 ta)\n"
            "• ⏱️ Quiz vaqtini sozlash (15-120 soniya)\n"
            "• ⚡ Ustuvor ishlov berish\n"
            "• 📊 2x katta fayllar\n\n"
            "💎 *Obuna tafsilotlari:*\n"
            "• Oylik obuna\n"
            "• Avtomatik yangilanish\n"
            "Obunani faollashtirish uchun tugmani bosing:"
        ),
        "success": (
            "✨ *Premium muvaffaqiyatli faollashtirildi!* ✨\n\n"
            "💫 *To‘lov tafsilotlari:*\n"
            "• Miqdor: {amount} UZS\n"
            "• Valyuta: {currency}\n\n"
            "📅 *Obuna muddati:*\n"
            "• Boshlanishi: {start}\n"
            "• Tugashi: {end}\n\n"
            "🌟 *Premium imkoniyatlar faollashtirildi:*\n"
            "• 📝 Savollar sonini sozlash (5-20 ta)\n"
            "• ⏱️ Quiz vaqtini sozlash (15-120 soniya)\n"
            "• ⚡ Ustuvor ishlov berish\n"
            "• 📊 Kengaytirilgan statistika\n\n"
            "💡 *Maslahat:* /settings orqali sozlang"
        ),
        "invoice": (
            "Premium SimpleQuiz obunasi: "
            "Savollar soni (5-20), vaqt (15-120s), ustuvor ishlov"
            "Oylik obuna, avtomatik yangilanish."
        )
    }
}


LEADERBOARD_TEXTS = {
    "en": {
        "results": "🏆 <b>{quiz_title} Results</b>",
        "total_questions": "📊 <b>Total questions:</b> {total}",
        "participants": "👥 <b>Participants:</b> {count}",
        "no_participants": "🏆 <b>Quiz Completed</b>\n\n❌ No participants found or no scores recorded.",
        "congrats": "🎉 Congratulations to <b>{winner}</b> for taking 1st place!",
        "minute": "minute",
        "minutes": "minutes",
        "second": "second",
        "seconds": "seconds"
    },
    "ru": {
        "results": "🏆 <b>Результаты {quiz_title}</b>",
        "total_questions": "📊 <b>Всего вопросов:</b> {total}",
        "participants": "👥 <b>Участников:</b> {count}",
        "no_participants": "🏆 <b>Викторина завершена</b>\n\n❌ Нет участников или не записано ни одного результата.",
        "congrats": "🎉 Поздравляем <b>{winner}</b> с первым местом!",
        "minute": "минута",
        "minutes": "минут",
        "second": "секунда",
        "seconds": "секунд"
    },
    "uz": {
        "results": "🏆 <b>{quiz_title} natijalari</b>",
        "total_questions": "📊 <b>Jami savollar:</b> {total}",
        "participants": "👥 <b>Ishtirokchilar:</b> {count}",
        "no_participants": "🏆 <b>Quiz yakunlandi</b>\n\n❌ Hech qanday ishtirokchi yoki natija yo‘q.",
        "congrats": "🎉 1-o‘rinni olgan <b>{winner}</b>ni tabriklaymiz!",
        "minute": "daqiqa",
        "minutes": "daqiqa",
        "second": "soniya",
        "seconds": "soniya"
    }
}


VALIDATION_ERRORS = {
    "en": {
        "title": "❌ Content Validation Failed",
        "reason": "Reason:",
        "instruction": "Please provide educational content such as articles, explanations, or detailed learning materials.",
        "restart": "To start again, please type /start"
    },
    "ru": {
        "title": "❌ Проверка контента не удалась", 
        "reason": "Причина:",
        "instruction": "Пожалуйста, предоставьте образовательный контент, такой как статьи, объяснения или подробные учебные материалы.",
        "restart": "Чтобы начать заново, введите /start"
    },
    "uz": {
        "title": "❌ Bu kontentdan quiz tuzib bo'lmaydi",
        "reason": "Sabab:",
        "instruction": "1 so'zli tushunarsiz textlar, yoki shunchaki salom- aliklar va shunga o'xshash kontentlardan savollar tuzib bo'lmaydi. Iltimos, maqolalar, tushuntirishlar yoki batafsil o'quv materiallari kabi ta'lim kontentini taqdim eting.",
        "restart": "Qaytadan boshlash uchun /start yozing"
    }
}


SUBSCRIPTION_TRANSLATIONS = {
    "en": {
        "subscription_required_single": "🔒 To use this bot, you need to subscribe to our channel first!",
        "subscription_required_multiple": "🔒 To use this bot, you need to subscribe to our channels first!",
        "subscription_instruction": "Please subscribe to the channel(s) below and then click 'Check Subscription' to continue:",
        "check_subscription": "✅ Check Subscription",
        "subscription_success": "✅ Great! You are now subscribed to all required channels. You can use the bot!",
        "subscription_incomplete": "❌ You are still not subscribed to all required channels. Please subscribe and try again."
    },
    "ru": {
        "subscription_required_single": "🔒 Для использования бота нужно подписаться на наш канал!",
        "subscription_required_multiple": "🔒 Для использования бота нужно подписаться на наши каналы!",
        "subscription_instruction": "Пожалуйста, подпишитесь на канал(ы) ниже и нажмите 'Проверить подписку' для продолжения:",
        "check_subscription": "✅ Проверить подписку",
        "subscription_success": "✅ Отлично! Теперь вы подписаны на все необходимые каналы. Можете пользоваться ботом!",
        "subscription_incomplete": "❌ Вы все еще не подписаны на все необходимые каналы. Пожалуйста, подпишитесь и попробуйте снова."
    }
}


MANUAL_PAYMENT_MESSAGES = {
    'uz': {
        'premium_payment': """💳 Premium obunani sotib olish uchun:

💰 <b>Narxi</b>: 30,000 so'm
📞 <b>To'lov muddati</b>: 30 kun

📋 <b>To'lov qilish tartibi</b>:
1️⃣ Quyidagi karta raqamiga pul o'tkazing:
   <code>{card_number}</code>

2️⃣ To'lov chekini admin @SimpleLearn_main_admin ga yuboring

3️⃣ Premium obuna avtomatik faollashtiriladi

⚠️ <b>Muhim</b>: Chekni yuborishni unutmang, aks holda obuna faollashtrilmaydi""",

        'balance_topup': """💳 Balansni to'ldirish uchun:

💰 <b>Minimal miqdor</b>: 1,000 so'm
💰 <b>Maksimal miqdor</b>: 100,000 so'm

📋 <b>To'lov qilish tartibi</b>:
1️⃣ Quyidagi karta raqamiga kerakli miqdorni o'tkazing:
   <code>{card_number}</code>

2️⃣ To'lov chekini admin @SimpleLearn_main_admin ga yuboring

3️⃣ Balans avtomatik to'ldiriladi

⚠️ <b>Muhim</b>: Chekni yuborishni unutmang!""",

        'payment_pending': """⏳ <b>To'lov kutilmoqda</b>

Agar to'lov amalga oshirilgan bo'lsa:
• To'lov chekini @SimpleLearn_main_admin ga yuboring
• 24 soat ichida balans to'ldiriladi yoki premium faollashtiriladi

❓ Savollar bo'lsa @SimpleLearn_main_admin ga murojaat qiling"""
    },
    'ru': {
        'premium_payment': """💳 Для покупки Premium подписки:

💰 <b>Цена</b>: 30,000 сум
📞 <b>Срок</b>: 30 дней

📋 <b>Порядок оплаты</b>:
1️⃣ Переведите деньги на следующую карту:
   <code>{card_number}</code>

2️⃣ Отправьте чек оплаты админу @SimpleLearn_main_admin

3️⃣ Premium подписка будет автоматически активирована

⚠️ <b>Важно</b>: Не забудьте отправить чек, иначе подписка не активируется""",

        'balance_topup': """💳 Для пополнения баланса:

💰 <b>Минимальная сумма</b>: 1,000 сум
💰 <b>Максимальная сумма</b>: 100,000 сум

📋 <b>Порядок оплаты</b>:
1️⃣ Переведите нужную сумму на карту:
   <code>{card_number}</code>

2️⃣ Отправьте чек оплаты админу @SimpleLearn\\_admin

3️⃣ Баланс будет автоматически пополнен

⚠️ <b>Важно</b>: Не забудьте отправить чек!""",

        'payment_pending': """⏳ <b>Ожидается оплата</b>

Если оплата уже произведена:
• Отправьте чек оплаты @SimpleLearn\\_admin
• Баланс будет пополнен или premium активирован в течение 24 часов

❓ Вопросы? Обращайтесь к @SimpleLearn\\_admin"""
    },
    'en': {
        'premium_payment': """💳 To purchase Premium subscription:

💰 <b>Price</b>: 30,000 UZS
📞 <b>Duration</b>: 30 days

📋 <b>Payment procedure</b>:
1️⃣ Transfer money to the following card:
   <code>{card_number}</code>

2️⃣ Send payment receipt to admin @SimpleLearn_main_admin

3️⃣ Premium subscription will be automatically activated

⚠️ <b>Important</b>: Don't forget to send the receipt, otherwise subscription won't be activated""",

        'balance_topup': """💳 To top up balance:

💰 <b>Minimum amount</b>: 1,000 UZS
💰 <b>Maximum amount</b>: 100,000 UZS

📋 <b>Payment procedure</b>:
1️⃣ Transfer the required amount to the card:
   <code>{card_number}</code>

2️⃣ Send payment receipt to admin @SimpleLearn_main_admin

3️⃣ Balance will be automatically topped up

⚠️ <b>Important</b>: Don't forget to send the receipt!""",

        'payment_pending': """⏳ <b>Payment pending</b>

If payment has been made:
• Send payment receipt to @SimpleLearn_main_admin
• Balance will be topped up or premium activated within 24 hours

❓ Questions? Contact @SimpleLearn_main_admin"""
    }
}



INFO_TEXTS = {
    "en": (
        "👤 <b>Bot Creator:</b> <a href='https://t.me/Muslimbek_01'>@Muslimbek_01</a>\n"
        "The Goal is making education more simple and accessible for everyone around the world. 🌍\n\n"
        "🤖 <b>Discover Our Other Bots:</b>\n"
        "• <a href='https://t.me/SimpleQuizzer_bot'>@SimpleQuizzer_bot</a> — Create fun & professional quizzes in seconds with AI.\n"
        "• <a href='https://t.me/SimplePresentation_maker_bot'>@SimplePresentation_maker_bot</a> — Instantly generate high-quality presentations with AI.\n"
        "• <a href='https://t.me/SimpleStudyy_bot'>@SimpleStudyy_bot</a> — Helps you to find scholarships and study grants!\n\n"

        "📢 <b>Join Our Community:</b>\n"
        "• <a href='https://t.me/simplelearnuz'>Simple Learn</a> — Be the first to know about our latest projects, updates, and opportunities.\n\n"
        "📝 <b>We Value Your Feedback:</b>\n"
        "• <a href='https://t.me/feedback_simplelearn'>Share your thoughts</a> — Your ideas and suggestions help us grow and improve. 💡\n\n"
        "✨ Stay curious, keep learning, and let’s build the future of education together!"
    ),
    "ru": (
        "👤 <b>Создатель бота:</b> <a href='https://t.me/Muslimbek_01'>@Muslimbek_01</a>\n"
        "Он вдохновлен идеей сделать образование проще и доступнее для всех! 🌍\n\n"
        "🤖 <b>Откройте для себя другие наши боты:</b>\n"
        "• <a href='https://t.me/SimpleQuizzer_bot'>@SimpleQuizzer_bot</a> — Создавайте интересные викторины за считанные секунды с помощью ИИ.\n"
        "• <a href='https://t.me/SimplePresentation_maker_bot'>@SimplePresentation_maker_bot</a> — Генерируйте качественные презентации мгновенно.\n"
        "• <a href='https://t.me/SimpleStudyy_bot'>@SimpleStudyy_bot</a> — Помогает найти стипендии и гранты на обучение!\n\n"
        "📢 <b>Присоединяйтесь к нашему сообществу:</b>\n"
        "• <a href='https://t.me/simplelearnuz'>Simple Learn</a> — Первым узнавайте о новых проектах, обновлениях и возможностях.\n\n"
        "📝 <b>Мы ценим вашу обратную связь:</b>\n"
        "• <a href='https://t.me/feedback_simplelearn'>Поделитесь своим мнением</a> — Ваши идеи и советы помогают нам становиться лучше. 💡\n\n"
        "✨ Оставайтесь любознательными, учитесь каждый день и давайте вместе строить будущее образования!"
    ),
    "uz": (
        "👤 <b>Bot yaratuvchisi:</b> <a href='https://t.me/Muslimbek_01'>@Muslimbek_01</a>\n"
        "Maqsad — ta’limni yanada qulay va hammaga ochiq qilish. 🌍\n\n"
        "🤖 <b>Boshqa botlarimizni ham sinab ko‘ring:</b>\n"
        "• <a href='https://t.me/SimpleQuizzer_bot'>@SimpleQuizzer_bot</a> — AI yordamida oson va qiziqarli viktorinalar tuzing.\n"
        "• <a href='https://t.me/SimplePresentation_maker_bot'>@SimplePresentation_maker_bot</a> — AI yordamida sifatli taqdimotlarni tezda yarating.\n"
        "• <a href='https://t.me/SimpleStudyy_bot'>@SimpleStudyy_bot</a> — Sizga stipendiyalar va o‘qish uchun grantlarni topishda yordam beradi!\n\n"
        "📢 <b>Bizning jamoamizga qo‘shiling:</b>\n"
        "• <a href='https://t.me/simplelearnuz'>Simple Learn</a> — Yangi loyihalar, yangiliklar va imkoniyatlardan birinchi bo‘lib xabardor bo‘ling.\n\n"
        "📝 <b>Fikringiz biz uchun juda muhim:</b>\n"
        "• <a href='https://t.me/feedback_simplelearn'>O‘z fikrlaringizni yozib qoldiring</a> — Sizning takliflaringiz bizni yanada yaxshiroq qilishga yordam beradi. 💡\n\n"
    ),
}


# --- DMTT branding (on when TABLE_SET=dmtt / BRAND=dmtt) ---
from src.brand import IS_DMTT, apply_brand, INFO_TEXTS_DMTT
if IS_DMTT:
    TRANSLATIONS = apply_brand(TRANSLATIONS)
    INFO_TEXTS = INFO_TEXTS_DMTT
