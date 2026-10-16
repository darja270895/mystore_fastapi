import {useDisclosure} from "@mantine/hooks";
import {useState} from 'react'
import {MainPage} from '../MainPage'
import {LoginModal} from "../LoginModal";
import {AdminPanelPage} from "../admin-panel/AdminPanelPage";


const AppMain = () => {
    const [opened, {open: showModal, close: hideModal}] = useDisclosure(false)
    const [isLoggedIn, setIsLoggedIn] = useState(() => {
        const user = localStorage.getItem('user');
        return user !== null;
    })

    const handleLogout = () => {
        localStorage.removeItem('user');
        setIsLoggedIn(false);
    };

    const handleLoginSuccess = () => {
        setIsLoggedIn(true);
        hideModal();
    };

    return (
        <>
            <MainPage onOpen={showModal} isLoggedIn={isLoggedIn}
                      onLogout={handleLogout}/>
            {/* {isLoggedIn && (
                <>
                    <UsersInfo/>
                    <ProductsInfo/>
                    <PurchaseList data={mockPurchases}/>
                </>
            )} */}
            {isLoggedIn && <AdminPanelPage/>}

            <LoginModal opened={opened} onClose={hideModal} onSuccess={handleLoginSuccess}/>
        </>
    )
}

export default AppMain;