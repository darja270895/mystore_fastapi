import { StrictMode } from 'react' // import only
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx' //main component

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
