###### src/ сновной исходный код

src/assets/ Статические ресурсы, которые импортируются из кода: изображения, SVG и т.п.



main.tsx // точка входа React приложения

App.tsx // Главный React-компонент приложения.

App.css // стили к App.tsx

index.css // глобальные стили

> npm run dev
> ↓
> Vite
> ↓
> index.html
> ↓
> main.tsx
> ↓
> App.tsx
> ↓
> React components



eslint.config.js // линтер js -> ts

tsconfig.json // конфигурация typescript

tsconfig.app.json //конфигурация typescript для frontend (React)

tsconfig.node.json // Node/Vite configuration

vite.config.ts // Vite config (proxy, dev server, plugins, build)

package.json // файл зависимостей, команд
