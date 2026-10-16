import {useQuery} from '@tanstack/react-query';
import {Box} from '@mantine/core';
import MyButton from '../ui/Button';
import MyTable from '../ui/Table';
import {fetchProducts} from '../../api/products';
import {queryKeys} from '../../api/queryKeys';

const ProductsInfo = () => {
    const productsQuery = useQuery({
        queryKey: queryKeys.products,
        queryFn: fetchProducts,
    });

    const products = productsQuery.data ?? [];

    return (
        <Box className="dashboard-section">
            <MyButton
                label="Refresh"
                onClick={() => void productsQuery.refetch()}
                loading={productsQuery.isFetching}
            />
            <MyTable data={products as unknown as Record<string, unknown>[]} />
        </Box>
    );
};

export default ProductsInfo;
