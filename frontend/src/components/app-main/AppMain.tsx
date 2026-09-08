import UsersInfo from "../users-info/UsersInfo";
import ProductsInfo from "../products-info/ProductsInfo";
import PurchaseList from "../purchases/purchasesList";
import '../../App.css'

import {mockPurchases} from "../purchases/purchases.mock";

const AppMain = () => {
    return (
        <div className="app">
            <h1 className="dashboard-title">
                🛒 Store Dashboard
            </h1>
            <UsersInfo/>
            <ProductsInfo/>
            <PurchaseList data={mockPurchases}/>

        </div>
    )
}

export default AppMain;