# montag — مكتبة أداة Montag (ملفات عامة)

ملفات تقرؤها صفحات Montag على بلوجر عبر jsDelivr (بدل تضمينها داخل الصفحة):

- `data/styles` و`data/templates` و`data/examples`: الستايلات والقوالب والأمثلة (JSON).
- `fonts/`: الخطوط العربية (woff2 مقلَّصة) تُحمَّل عند الحاجة فقط.
- `dist/`: صفحات بلوجر الخفيفة (`*-cdn.html`) جاهزة للصق في بلوجر (عرض HTML).
- `version.json`: رقم الإصدار والرابط الأساسي.

## الروابط

الأساس مثبّت على رقم commit محدد (لا يتغير أبداً، وبالتالي لا مشكلة في الذاكرة المؤقتة):
`https://cdn.jsdelivr.net/gh/ahmedmher/monsinfopubilc@350855f92a3f3e41a3b59466b346ecb3c2c28a58/montag/`

مثال: `.../montag/data/templates/index.json`

صفحات بلوجر الجاهزة في `dist/` تشير إلى هذا الأساس. الإصدار الحالي: انظر `version.json`.

## تحديث إصدار جديد

يُولَّد المحتوى من المستودع الخاص (`tools/publish-cdn.sh`) على خطوتين:
1. commit للبيانات والخطوط (يعطي رقم commit جديداً).
2. إعادة بناء الصفحات بحيث تشير إلى رقم ذلك الـ commit ثم commit ثانٍ للصفحات.
