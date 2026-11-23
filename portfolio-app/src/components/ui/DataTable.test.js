import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import DataTable from './DataTable';

const COLUMNS = [
  { key: 'name', label: 'Name', sortable: true },
  { key: 'balance', label: 'Balance', render: row => `Rs. ${row.balance.toFixed(2)}` },
  { key: 'note', label: 'Note' },
];

const ROWS = [
  { id: 1, name: 'HDFC', balance: 1000, note: 'Salary' },
  { id: 2, name: 'SBI', balance: 250.5 },
];

describe('DataTable', () => {
  test('shows a loading state instead of the table', () => {
    render(<DataTable columns={COLUMNS} data={ROWS} loading />);

    expect(screen.getByRole('status')).toHaveTextContent('Loading...');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  test('shows the empty message when there is no data', () => {
    render(<DataTable columns={COLUMNS} data={[]} emptyMessage="No banks found" />);

    expect(screen.getByText('No banks found')).toBeInTheDocument();
  });

  test('renders rows, custom cell renderers and "-" for missing values', () => {
    render(<DataTable columns={COLUMNS} data={ROWS} />);

    const rows = screen.getAllByRole('row');
    // header + 2 data rows
    expect(rows).toHaveLength(3);

    const firstRow = within(rows[1]).getAllByRole('cell').map(c => c.textContent);
    expect(firstRow).toEqual(['HDFC', 'Rs. 1000.00', 'Salary']);

    const secondRow = within(rows[2]).getAllByRole('cell').map(c => c.textContent);
    expect(secondRow).toEqual(['SBI', 'Rs. 250.50', '-']);
  });

  test('calls onSort only for sortable columns and shows the sort arrow', async () => {
    const onSort = jest.fn();
    const user = userEvent.setup();

    render(
      <DataTable
        columns={COLUMNS}
        data={ROWS}
        onSort={onSort}
        sortBy="name"
        sortDirection="desc"
      />
    );

    expect(screen.getByRole('columnheader', { name: /Name/ })).toHaveTextContent('▼');

    await user.click(screen.getByRole('columnheader', { name: /Name/ }));
    await user.click(screen.getByRole('columnheader', { name: 'Balance' }));

    expect(onSort).toHaveBeenCalledTimes(1);
    expect(onSort).toHaveBeenCalledWith('name');
  });

  test('renders an actions column and a footer when provided', () => {
    render(
      <DataTable
        columns={COLUMNS}
        data={ROWS}
        renderActions={row => <button type="button">Edit {row.name}</button>}
        renderFooter={() => (
          <tr>
            <td>Totals</td>
          </tr>
        )}
      />
    );

    expect(screen.getByRole('columnheader', { name: 'Actions' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Edit HDFC' })).toBeInTheDocument();
    expect(screen.getByText('Totals')).toBeInTheDocument();
  });
});
