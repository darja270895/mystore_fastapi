import {Button,} from '@mantine/core'
import type {ButtonProps} from '@mantine/core'
import '@mantine/core/styles.css';

interface CustomButtonProps extends ButtonProps {
    label: string;
    onClick: () => void;
    loading?: boolean;
}

export default function MyButton({label, onClick, loading, ...others}: CustomButtonProps) {
    return (
        <Button
            onClick={onClick}
            loading={loading}
            variant="gradient"
            gradient={{from: 'teal', to: 'cyan', deg: 90}}
            style={{
                position: 'absolute',
                right: '30px',
                padding: '10px 16px',
                '&:hover': {
                    background: '#6493aa', // Overrides the gradient on hover
                },
                '&:active': {
                    transform: 'translateY(1px)', // Gives it a "pressed" effect
                }
            }}
            {...others}
        >

            {label}

        </Button>
    );
}