توضیح ساده · دانش کامپیوتر

# چرا وقتی فضای ذخیره‌سازی تقریباً پر است، کامپیوتر کند می‌شود؟

درایو عکس‌ها و اسناد را نگه می‌دارد، اما برای کار کردن کامپیوتر هم فضا فراهم می‌کند. سه فعالیت پشت صحنه توضیح می‌دهند چرا کمبود فضا می‌تواند مشکل‌ساز شود.

نوشتهٔ [احمدرضا صمدی](https://a-samadi.com/fa/about.html) · ۹ اکتبر ۲۰۲۶ · [نسخهٔ انگلیسی](https://a-samadi.com/writing/why-full-storage-slows-computer.html)

به‌روزرسانی ۱۰ اکتبر ۲۰۲۶

## در یک نگاه

کاروسل اصلی با رنگ مرجانی پاستلی. نوار فضای ذخیره‌سازی صرفاً تصویرسازی است، نه درصد پیشنهادی.

## کارهای موقت

به‌روزرسانی، ذخیره و خروجی گرفتن ممکن است فضای اضافه بخواهند.

## سرریز حافظه

وقتی رم مشغول است، داده‌های کم‌استفاده ممکن است به درایو منتقل شوند.

## کارهای داخلی SSD

نوشتن داده جدید گاهی نیازمند جابه‌جایی داده موجود است.

## ۱. چرا به‌روزرسانی ممکن است بیشتر از اندازهٔ دانلودش فضا بخواهد؟

بسته دانلودشده ممکن است برای باز کردن فایل‌ها، نصب و نگهداری فایل‌های بازیابی، فضای بیشتری بخواهد. برنامه‌ها هم هنگام ذخیره یا خروجی گرفتن فایل‌های موقت می‌سازند. کمبود فضا می‌تواند کار را متوقف یا ناموفق کند، نه اینکه فقط آن را کندتر کند.

منبع: [Microsoft: Free up space for Windows updates](https://support.microsoft.com/en-gb/windows/deployment/updates-lifecycle/free-up-space-for-windows-updates)

## ۲. وقتی رم مشغول است، کامپیوتر چگونه از فضای ذخیره‌سازی استفاده می‌کند؟

رم حافظه سریع برای کارهای همین لحظه است؛ درایو فایل‌ها را برای مدت طولانی‌تر نگه می‌دارد. وقتی رم مشغول است، سیستم می‌تواند داده‌های کم‌استفاده را به درایو منتقل کند. ویندوز از page file و مک از swap استفاده می‌کند. این روش از رم کندتر است و فضای درایو می‌خواهد. علت آن فشار بر حافظه است، نه صرفاً پر بودن درایو. آزاد کردن فضای ذخیره‌سازی، رم را افزایش نمی‌دهد.

منبع: [Apple: View memory usage in Activity Monitor](https://support.apple.com/guide/activity-monitor/view-memory-usage-actmntr1004/mac) · [Microsoft Learn: Introduction to page files](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/introduction-to-the-page-file)

## ۳. چرا SSD هنگام نوشتن دادهٔ جدید ممکن است دادهٔ موجود را جابه‌جا کند؟

SSD محل ذخیره‌سازی بیشتر لپ‌تاپ‌های امروزی است. حافظه فلش داده را در قطعات کوچک می‌نویسد، اما گروه‌های بزرگ‌تری به نام بلوک را پاک می‌کند. برای استفاده دوباره از بلوکی که بخشی از آن اشغال است، ممکن است داده لازم را به جای دیگری ببرد، بلوک قدیمی را پاک کند و دوباره از آن استفاده کند. بلوک‌های آزاد کمتر می‌تواند جابه‌جایی هنگام نوشتن را بیشتر کند.

منبع: [Kingston: Garbage collection](https://www.kingston.com/en/blog/servers-and-data-centers/garbage-collection)

## چرا درصد جادویی وجود ندارد؟

اثر به مدل SSD، نوع کار، TRIM و ظرفیت رزروشده داخلی بستگی دارد. TRIM کمک می‌کند درایو بفهمد کدام داده دیگر لازم نیست. فضای آزادی که می‌بینید با ذخیره داخلی درایو یکسان نیست. به‌روزرسانی بزرگ یا خروجی ویدئو می‌تواند خیلی بیشتر از مرور وب فضا بخواهد. کمبود فضا لزوماً همه خواندن‌ها یا کارهای پردازنده را کند نمی‌کند.

منبع: [Kingston: SSD FAQs](https://www.kingston.com/en/ssd/ssd-faq)

## جا باز کنید؛ چیزهای مهم را نگه دارید

از تنظیمات داخلی ذخیره‌سازی شروع کنید. فایل‌های بزرگ، برنامه‌های بلااستفاده و پیشنهادهای پاک‌سازی را بررسی کنید. پیش از حذف فایل مهم، نسخه پشتیبان تهیه کنید و پیش از خالی کردن سطل زباله، محتویاتش را ببینید. برای کار بعدی فضا نگه دارید؛ یک درصد ثابت برای همه وجود ندارد.

منبع: [Microsoft: Free up drive space in Windows](https://support.microsoft.com/en-us/windows/experience/storage-filemanagement/free-up-drive-space-in-windows)

مک: تنظیمات سیستم ← عمومی ← فضای ذخیره‌سازی

ویندوز: تنظیمات ← سیستم ← فضای ذخیره‌سازی

## هنوز کند است؟ فضای ذخیره‌سازی فقط یکی از علت‌هاست

برنامه‌های پرکار و فشار بر حافظه را بررسی کنید. درایو تقریباً پر و رم ناکافی دو مشکل جدا هستند، هرچند می‌توانند بر هم اثر بگذارند.

منبع: [Apple: If your Mac runs slowly](https://support.apple.com/guide/mac-help/if-your-mac-runs-slowly-mchlp1731/mac)

## توضیح در ده اسلاید

نمودارهای ساده و اصلی هستند، نه تصویر محصول یا نتایج اندازه‌گیری. هر ده اسلاید به انگلیسی‌اند.

نمایش هر ۱۰ اسلاید انگلیسی

اسلاید 1 / 10

اسلاید 2 / 10

اسلاید 3 / 10

اسلاید 4 / 10

اسلاید 5 / 10

اسلاید 6 / 10

اسلاید 7 / 10

اسلاید 8 / 10

اسلاید 9 / 10

اسلاید 10 / 10

[دانلود کاروسل انگلیسی به صورت PDF](https://a-samadi.com/assets/writing/almost-full-storage/almost-full-storage-carousel.pdf)

## منتشرشده در

[Instagram](https://www.instagram.com/p/DeRD_FgCutT/) · [LinkedIn](https://www.linkedin.com/feed/update/urn:li:activity:7514238957828878336/) · [YouTube](https://www.youtube.com/post/UgkxPgMXxjFKMvohuq9zSIRxVrSlMkCPrbKp)

## منابع

منابع اصلی در ۹ اکتبر ۲۰۲۶ بررسی شده‌اند. آستانه دقیق کند شدن یا بهبود سرعت تضمینی ادعا نشده است.

- [Apple: If your Mac runs slowly](https://support.apple.com/guide/mac-help/if-your-mac-runs-slowly-mchlp1731/mac)

- [Microsoft: Free up drive space in Windows](https://support.microsoft.com/en-us/windows/experience/storage-filemanagement/free-up-drive-space-in-windows)

- [Microsoft: Free up space for Windows updates](https://support.microsoft.com/en-gb/windows/deployment/updates-lifecycle/free-up-space-for-windows-updates)

- [Apple: View memory usage in Activity Monitor](https://support.apple.com/guide/activity-monitor/view-memory-usage-actmntr1004/mac)

- [Microsoft Learn: Introduction to page files](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/introduction-to-the-page-file)

- [Kingston: Garbage collection](https://www.kingston.com/en/blog/servers-and-data-centers/garbage-collection)

- [Kingston: SSD FAQs](https://www.kingston.com/en/ssd/ssd-faq)
