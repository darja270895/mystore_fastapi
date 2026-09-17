import UsersInfo from "../users-info/UsersInfo";
import ProductsInfo from "../products-info/ProductsInfo";
import PurchaseList from "../purchases/purchasesList";
import {mockPurchases} from "../purchases/purchases.mock";
import {useDisclosure} from "@mantine/hooks";
import {useState} from 'react'
import {MainPage} from '../MainPage'
import {LoginModal} from "../LoginModal";


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
    return (
        <>
            <MainPage onOpen={showModal} isLoggedIn={isLoggedIn}
                      onLogout={handleLogout}/>
            {isLoggedIn && (
                <>
                    <UsersInfo/>
                    <ProductsInfo/>
                    <PurchaseList data={mockPurchases}/>
                </>
            )}

            <LoginModal opened={opened} onClose={hideModal}/>


        </>
    )
}

export default AppMain;