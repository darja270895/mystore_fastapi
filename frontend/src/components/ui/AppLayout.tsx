import { Box } from '@mantine/core';

// Main Theme for the whole App

interface AppLayoutProps {
    children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
    return (
        <Box
            style={{
        minHeight: '100vh',
            padding: '32px 48px 60px',

            background: `
          linear-gradient(
            rgba(30, 52, 66, 0.72),
            rgba(30, 52, 66, 0.82)
          ),
          url('/src/assets/background_img.jpg')
        `,

            backgroundSize: 'cover',
            backgroundPosition: 'center',
            backgroundAttachment: 'fixed',
    }}
>
    {children}
    </Box>
);
}