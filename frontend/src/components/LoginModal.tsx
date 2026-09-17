import {Button, Center, Modal, Stack, TextInput} from "@mantine/core";
import {useState} from 'react'
import {handleRefresh} from "../pageFunctionality";
interface LoginModalProps {
    opened: boolean;
    onClose: () => void;
}

export function LoginModal({opened, onClose}: LoginModalProps) {

    const [formData, setFormData] = useState({
        firstname: '',
        surname: '',
        email: '',
        password: '',
    });

    const handleChange = (event) => {
        const {name, value} = event.currentTarget;

        setFormData(prevValue => ({
            ...prevValue,
            [name]: value,
        }));
    };
    const handleSubmit = () => {
        localStorage.setItem('user', JSON.stringify(formData))
        onClose();
        handleRefresh();
    };

    return (
        <>
            <Modal opened={opened} onClose={onClose} centered withCloseButton={false}>
                <Stack>
                    <h3>Hello {formData.firstname}</h3>
                    <h1 style={{marginTop: 0}}>Registration form</h1>

                    <TextInput label="First name" name='firstname' placeholder="Enter your name"
                               onChange={handleChange}/>
                    <TextInput label="Surname" name='surname' placeholder="Enter your surname" onChange={handleChange}/>
                    <TextInput label="Email" name='email' placeholder="Enter email" onChange={handleChange}/>
                    <TextInput label="Password" name='password' placeholder="Password" onChange={handleChange}/>
                    <Center mt="md">
                        <Button onClick={handleSubmit}>Save</Button>
                    </Center>
                </Stack>
            </Modal>
        </>
    )
}