# مكتبة Skills بالعربي

- `sources.json`: قائمة المستودعات العامة التي تُسحب منها الـ skills (أضف مستودعا جديدا هنا فقط).
- `update_skills.py`: يسحب الـ skills ويترجم الوصف ويصنّف ويجلب الصورة/الفيديو الرئيسي، ويكتب `skills.json`.
- `blogger-page.html`: الصفحة كاملة، تُلصق في صفحة بلوجر (وضع HTML). التفاصيل تُفتح على نفس الرابط بـ `#sk/اسم`.
- الـ Action في `.github/workflows/update-ai-skills.yml` تعمل يوميا. أضف سر `ANTHROPIC_API_KEY` في إعدادات المستودع (Settings ← Secrets) لتفعيل الترجمة والتصنيف الذكي، وبدونه تظهر الأوصاف بالإنجليزية.
