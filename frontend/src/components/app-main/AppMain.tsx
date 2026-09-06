import UsersInfo from "../users-info/UsersInfo.tsx";
import ProductsInfo from "../products-info/ProductsInfo.tsx";
import '../../App.css'

const AppMain = () => {
    return (
        <div className="app">
            <h1 className="dashboard-title">
                🛒 Store Dashboard
            </h1>
            <UsersInfo/>
            <ProductsInfo/>

        </div>
    )
}

export default AppMain;