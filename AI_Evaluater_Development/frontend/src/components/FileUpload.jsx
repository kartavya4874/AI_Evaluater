import React from 'react';

const FileUpload = ({ label, onChange, accept = ".pdf", disabled = false }) => {
  return (
    <div className="file-upload">
      <label className="file-label">{label}</label>
      <input
        type="file"
        accept={accept}
        onChange={onChange}
        disabled={disabled}
        className="file-input"
      />
    </div>
  );
};

export default FileUpload;
