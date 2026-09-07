import React from 'react';

function DataTable({
  columns = [],
  data = [],
  rowKey = 'id',
  loading = false,
  emptyMessage = 'No data found.',
  onSort,
  sortBy,
  sortDirection = 'asc',
  renderActions,
  renderFooter,
}) {
  if (loading) {
    return (
      <div className="table-loading" role="status">
        Loading...
      </div>
    );
  }

  const columnCount = columns.length + (renderActions ? 1 : 0);

  return (
    <div className="table-container">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map(column => {
              const sortable = Boolean(column.sortable);

              return (
                <th
                  key={column.key}
                  scope="col"
                  className={sortable ? 'sortable' : ''}
                  onClick={
                    sortable && onSort
                      ? () => onSort(column.key)
                      : undefined
                  }
                >
                  {column.label}

                  {sortable && sortBy === column.key && (
                    <span aria-hidden="true">
                      {sortDirection === 'asc' ? ' ▲' : ' ▼'}
                    </span>
                  )}
                </th>
              );
            })}

            {renderActions && (
              <th scope="col">
                Actions
              </th>
            )}
          </tr>
        </thead>

        <tbody>
          {data.length === 0 ? (
            <tr>
              <td colSpan={columnCount}>
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, index) => {
              const key =
                typeof rowKey === 'function'
                  ? rowKey(row)
                  : row[rowKey];

              return (
                <tr key={key ?? index}>
                  {columns.map(column => (
                    <td key={column.key}>
                      {column.render
                        ? column.render(row)
                        : row[column.key] ?? '-'}
                    </td>
                  ))}

                  {renderActions && (
                    <td className="actions-cell">
                      {renderActions(row)}
                    </td>
                  )}
                </tr>
              );
            })
          )}
        </tbody>

        {renderFooter && data.length > 0 && (
          <tfoot>
            {renderFooter(data)}
          </tfoot>
        )}
      </table>
    </div>
  );
}

export default DataTable;