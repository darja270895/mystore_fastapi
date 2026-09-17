import {UsersIcon} from "@phosphor-icons/react";

import {clearLocaltorage} from "../pageFunctionality";

import {
    Box,
    Button,
    Container,
    Flex,
    Group,
    Stack,
    Text,
    ThemeIcon,
    Title,
} from '@mantine/core';
import {
    IconUsers,
    IconShoppingCart,
} from '@tabler/icons-react';



export function MainPage({onOpen, isLoggedIn, onLogout}) {
    return (
        <Box>
            <Container size="lg" py="md">
                {/*justify="flex-end"*/}
                <Group gap="xs">
                    <ThemeIcon size="lg" radius="md" variant="gradient" gradient={{ from: 'indigo', to: 'cyan' }}>
                        <IconShoppingCart size={20} />
                    </ThemeIcon>
                    <Title order={3}>🛒 Store Dashboard</Title>
                </Group>
                <Flex justify="flex-end">

                    <Group>
                        {isLoggedIn ? (
                            <Button
                                leftSection={<IconUsers size={18} />}
                                variant="default"
                                onClick={onLogout}
                            >
                                Logout
                            </Button>
                        ) : (
                            <Button
                                leftSection={<IconUsers size={18} />}
                                variant="gradient"
                                gradient={{ from: 'indigo', to: 'cyan' }}
                                onClick={onOpen}
                            >
                                Login
                            </Button>
                        )}
                    </Group>
                </Flex>
            </Container>

            {!isLoggedIn ? (
                <>
            {/* Hero section */}
            <Container size="lg" py={{ base: 'xl', md: 80 }}>
                <Stack align="center" gap="lg" maw={720} mx="auto" ta="center">
                    <Title
                        order={1}
                        style={{ fontSize: 'clamp(2rem, 5vw, 3.5rem)', lineHeight: 1.1 }}
                    >
                        Manage your store{' '}
                        <Text
                            component="span"
                            inherit
                            variant="gradient"
                            gradient={{ from: 'indigo', to: 'cyan' }}
                            fw={900}
                        >
                            effortlessly
                        </Text>
                    </Title>

                    <Text size="lg" c="dimmed">
                        Track products, manage users, and monitor purchases — all from a single,
                        beautiful dashboard built for modern teams.
                    </Text>

                    <Group mt="md">
                        <Button
                            size="md"
                            variant="gradient"
                            gradient={{ from: 'indigo', to: 'cyan' }}
                            onClick={onOpen}
                        >
                            Get started
                        </Button>
                        <Button size="md" variant="default">
                            Learn more
                        </Button>
                    </Group>
                </Stack>
            </Container> </>): <></>
            }

            {/*<LoginModal opened={opened} onClose={onClose}/>*/}

        </Box>
    )
}