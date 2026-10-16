import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import {MantineProvider} from '@mantine/core';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import '@mantine/core/styles.css';
import './index.css';
import App from './App.tsx';

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            retry: 1,
            refetchOnWindowFocus: false,
        },
    },
});

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <QueryClientProvider client={queryClient}>
            <MantineProvider defaultColorScheme="dark">
                <App />
            </MantineProvider>
        </QueryClientProvider>
    </StrictMode>,
);
