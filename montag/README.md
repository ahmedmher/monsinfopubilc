# montag — مكتبة أداة Montag (ملفات عامة)

ملفات تقرؤها صفحات Montag على بلوجر عبر jsDelivr (بدل تضمينها داخل الصفحة):

- `data/styles` و`data/templates` و`data/examples`: الستايلات والقوالب والأمثلة (JSON).
- `fonts/`: الخطوط العربية (woff2 مقلَّصة) تُحمَّل عند الحاجة فقط.
- `dist/`: صفحات بلوجر الخفيفة (`*-cdn.html`) جاهزة للصق في بلوجر (عرض HTML).
- `version.json`: رقم الإصدار والرابط الأساسي.

## الروابط

الأساس (ثابت على نسخة محددة — لا يتغير):
`https://cdn.jsdelivr.net/gh/ahmedmher/monsinfopubilc@montag-v2.7/montag/`

مثال: `.../montag/data/templates/index.json`

## تحديث إصدار جديد

يُولَّد المحتوى تلقائياً من المستودع الخاص بالأمر:

```
node tools/build-single.mjs --cdn=https://cdn.jsdelivr.net/gh/ahmedmher/monsinfopubilc@montag-vX.Y/montag --publish=<مسار monsinfopubilc>/montag
```

ثم commit وtag باسم `montag-vX.Y` (استخدم tag جديداً لكل إصدار حتى لا يبقى ملف قديم في ذاكرة jsDelivr المؤقتة).
