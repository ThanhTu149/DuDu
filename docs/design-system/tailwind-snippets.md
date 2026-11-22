# Snippets Tailwind tương ứng từng thành phần

Tương đương việc bật **Dev Mode** trong Figma rồi click từng phần tử. Dán vào dự án có
Tailwind; nếu dùng CSS thuần thì mở `web/assets/app.css`, các class tương ứng nằm cùng tên.

Bảng màu lấy từ `docs/design-system/tokens.json`: `paper #f5f2ec`, `paper-2 #faf8f4`,
`ink #1c1917`, `ink-2 #57534e`, `accent #c9490e`, `teal #2c6b52`, `alert #b3261e`.

## Nút chính

```html
<button class="inline-flex items-center gap-2 rounded-lg bg-[#c9490e] px-4 py-2.5
               text-[13px] font-semibold text-white shadow-sm
               hover:bg-[#b03f0b] focus-visible:outline focus-visible:outline-2
               focus-visible:outline-offset-2 focus-visible:outline-[#c9490e]">
  <svg class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
  Lập kế hoạch
</button>
```

## Nút phụ

```html
<button class="rounded-lg border border-[#ddd7cb] bg-transparent px-4 py-2
               text-[12.5px] font-medium text-[#57534e]
               hover:bg-[#efeae0] hover:text-[#1c1917]">So sánh</button>
```

## Thẻ KPI

```html
<div class="flex flex-col gap-0.5 border-l border-[#e9e4da] px-5 first:border-0 first:pl-0">
  <span class="text-[10.5px] tracking-wide text-[#57534e]">Tổng quãng đường</span>
  <span class="flex items-baseline gap-1 font-mono text-[18px] font-semibold text-[#1c1917]">
    160 <span class="text-[12.5px] font-medium text-[#57534e]">km</span>
  </span>
</div>
```

## Chip biển số xe

```html
<span class="inline-block rounded-[4px] bg-[#1c1917] px-[5px] py-[1px]
             font-mono text-[10.5px] font-semibold text-white">51G-160.82</span>
```

## Badge mức luật

```html
<span class="rounded-full bg-[#f8dfdc] px-2 py-[1px] text-[10px] text-[#b3261e]">chặn</span>
<span class="rounded-full bg-[#fbf0d6] px-2 py-[1px] text-[10px] text-[#8a6100]">cảnh báo</span>
```

## Marker sự cố trên bản đồ

Dùng tệp `web/assets/markers/xe-hong.svg` (48×58) đặt trên bản đồ:

```html
<img src="/assets/markers/ket-xe.svg" alt="Kẹt xe"
     class="absolute -translate-x-1/2 -translate-y-full w-[44px] drop-shadow-md" />
```

## Thẻ Biệt đội (mascot)

```html
<div class="absolute bottom-10 left-3.5 w-[222px] overflow-hidden rounded-xl
            border border-[#e5dccb] bg-[#faf5e8]/95 shadow-lg backdrop-blur">
  <img src="/assets/banner.jpg" class="aspect-[16/9.6] w-full object-cover"
       style="object-position:100% 34%" alt="Biệt đội DuDu" />
  <p class="truncate border-t border-[#e5dccb]/80 px-2.5 py-1.5
            text-[10.5px] text-[#57534e]">48 đơn tối ưu · Đúng giờ 97,9%</p>
</div>
```

## Tooltip rail trái

```html
<button class="group relative grid h-10 w-10 place-items-center rounded-lg
               text-white/60 hover:bg-white/10 hover:text-white">
  <svg class="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">…</svg>
  <span class="pointer-events-none absolute left-12 whitespace-nowrap rounded bg-[#262b33]
               px-2 py-1 text-[11px] text-[#f2efe8] opacity-0 transition
               group-hover:opacity-100">Điều phối</span>
</button>
```

## Lưu ý khi dựng lại trong Figma

1. Kéo `docs/design-system/figma-kit.png` vào Figma làm bảng tham chiếu; muốn layer sửa
   được thì kéo từng tệp `web/assets/stickers/*.png`, `web/assets/icons/*.svg`,
   `web/assets/markers/*.svg`.
2. Import `docs/design-system/tokens.studio.json` bằng plugin **Tokens Studio** để có biến
   màu/chữ.
3. Bộ icon dùng `stroke="currentColor"` nên trong Figma đổi màu bằng cách đổi `stroke`
   của group sau khi **Outline stroke**.
