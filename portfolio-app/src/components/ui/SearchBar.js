import React from 'react';

function SearchBar({
  value,
  onChange,
  placeholder = 'Search...',
  disabled = false,
  ariaLabel = 'Search',
}) {
  return (
    <input
      type="search"
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      disabled={disabled}
      aria-label={ariaLabel}
      className="search-input"
    />
  );
}

export default SearchBar;