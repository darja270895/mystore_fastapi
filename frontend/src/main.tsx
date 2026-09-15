import { StrictMode } from 'react' // import only
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import {MantineProvider} from "@mantine/core"; //main component

createRoot(document.getElementById('root')!).render(
  <StrictMode>
      <MantineProvider>
        <App />
      </MantineProvider>
  </StrictMode>,
)
