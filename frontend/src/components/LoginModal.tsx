import {Button, Center, Modal, Stack, TextInput, Title, Text} from '@mantine/core';
import {useState, type ChangeEvent} from 'react';

interface LoginModalProps {
    opened: boolean;
    onClose: () => void;
    onSuccess?: () => void;
}

export function LoginModal({opened, onClose, onSuccess}: LoginModalProps) {
    const [formData, setFormData] = useState({
        firstname: '',
        surname: '',
        email: '',
        password: '',
    });

    const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
        const {name, value} = event.currentTarget;
        setFormData((prevValue) => ({
            ...prevValue,
            [name]: value,
        }));
    };

    const handleSubmit = () => {
        localStorage.setItem('user', JSON.stringify(formData));
        onSuccess?.();
        onClose();
    };

    return (
        <Modal opened={opened} onClose={onClose} centered withCloseButton={false}>
            <Stack>
                {formData.firstname ? (
                    <Text>Hello {formData.firstname}</Text>
                ) : null}
                <Title order={2} mt={0}>Registration form</Title>

                <TextInput
                    label="First name"
                    name="firstname"
                    placeholder="Enter your name"
                    onChange={handleChange}
                />
                <TextInput
                    label="Surname"
                    name="surname"
                    placeholder="Enter your surname"
                    onChange={handleChange}
                />
                <TextInput
                    label="Email"
                    name="email"
                    placeholder="Enter email"
                    onChange={handleChange}
                />
                <TextInput
                    label="Password"
                    name="password"
                    type="password"
                    placeholder="Password"
                    onChange={handleChange}
                />
                <Center mt="md">
                    <Button
                        variant="gradient"
                        gradient={{from: 'indigo', to: 'cyan'}}
                        onClick={handleSubmit}
                    >
                        Save
                    </Button>
                </Center>
            </Stack>
        </Modal>
    );
}
