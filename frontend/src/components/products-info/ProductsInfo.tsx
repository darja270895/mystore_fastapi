import loadProducts from "./load-products";
import {useEffect, useState} from "react";
import MyButton from "../ui/Button"
import MyTable from "../ui/Table"
import {Box} from '@mantine/core'


interface Product {
    id: number;
    name: string;
    stock: string;
    price: number;
}


const ProductsInfo = () => {
    const [products, setProducts] = useState<Product[]>([]);
    const [isLoading, setIsLoading] = useState(false)

    async function handleLoadProducts() {
        setIsLoading(true)
        try {
            const users = await loadProducts();
            console.log(users);
            setProducts(users);
        } catch (error) {
            console.log("Error loading Products", error)
        } finally {
            setIsLoading(false)
        }
    }


    useEffect(() => {
        handleLoadProducts();
    }, []);

    return (
        <Box className="dashboard-section">
            <MyButton label='Refresh' onClick={handleLoadProducts} loading={isLoading}/>
                <MyTable data={products}/>

        </Box>
)
}

export default ProductsInfo;