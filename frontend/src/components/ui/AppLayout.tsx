import {Box} from '@mantine/core';
import backgroundImg from '../../assets/background_img.jpg';

interface AppLayoutProps {
    children: React.ReactNode;
} //read about React.ReactNode

export function AppLayout({children}: AppLayoutProps) {
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
          url(${backgroundImg})
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
