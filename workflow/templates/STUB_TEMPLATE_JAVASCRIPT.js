/**
 * Stub Implementation Template - JavaScript/TypeScript
 *
 * Purpose: Create minimal interface definitions to unblock parallel agent work.
 * When to use: When Agent B needs to call code that Agent A hasn't finished yet.
 *
 * Instructions:
 * 1. Copy this template
 * 2. Define the interface (function signatures, class methods)
 * 3. Throw NotImplementedError in all methods
 * 4. Add clear TODO comments indicating what needs implementation
 * 5. Document expected behavior in JSDoc comments
 */

/**
 * Custom error for stub methods
 */
class NotImplementedError extends Error {
  constructor(message) {
    super(message);
    this.name = 'NotImplementedError';
  }
}

/**
 * [STUB] Brief description of what this class does.
 *
 * TODO: Full implementation required by [Agent Name/Phase]
 * Dependencies: [List any dependencies]
 *
 * @class StubClass
 */
class StubClass {
  /**
   * Initialize the stub.
   *
   * @param {Object} [config={}] - Configuration object (format TBD)
   */
  constructor(config = {}) {
    this.config = config;
    // Add minimal initialization needed for type checking
  }

  /**
   * [STUB] Brief description of what this method should do.
   *
   * TODO: Implement by [Agent/Phase]
   * Expected behavior: [Describe expected behavior]
   *
   * @param {string} param1 - Description of param1
   * @param {number} param2 - Description of param2
   * @returns {Object} Object containing:
   *   - key1: Description
   *   - key2: Description
   * @throws {NotImplementedError} This is a stub
   *
   * @example
   * const result = instance.primaryMethod("test", 42);
   * // Expected result: { key1: ..., key2: ... }
   */
  primaryMethod(param1, param2) {
    throw new NotImplementedError('Stub: primaryMethod not yet implemented');
  }

  /**
   * [STUB] Brief description.
   *
   * TODO: Implement by [Agent/Phase]
   *
   * @param {Array} data - Input data
   * @returns {boolean} Success status
   * @throws {NotImplementedError} This is a stub
   */
  helperMethod(data) {
    throw new NotImplementedError('Stub: helperMethod not yet implemented');
  }

  /**
   * [STUB] Async method example.
   *
   * TODO: Implement by [Agent/Phase]
   *
   * @async
   * @param {any} input - Input parameter
   * @returns {Promise<Object>} Promise resolving to result object
   * @throws {NotImplementedError} This is a stub
   */
  async asyncMethod(input) {
    throw new NotImplementedError('Stub: asyncMethod not yet implemented');
  }
}

/**
 * [STUB] Brief description of what this function does.
 *
 * TODO: Implement by [Agent/Phase]
 *
 * @param {any} inputData - Description
 * @param {Object} [options={}] - Optional configuration
 * @returns {any} Description of return value
 * @throws {NotImplementedError} This is a stub
 *
 * @example
 * const result = stubFunction({ key: "value" });
 * // Expected result format: {...}
 */
function stubFunction(inputData, options = {}) {
  throw new NotImplementedError('Stub: stubFunction not yet implemented');
}

/**
 * [STUB] Async function example.
 *
 * TODO: Implement by [Agent/Phase]
 *
 * @async
 * @param {any} data - Input data
 * @returns {Promise<any>} Description of return value
 * @throws {NotImplementedError} This is a stub
 */
async function stubAsyncFunction(data) {
  throw new NotImplementedError('Stub: stubAsyncFunction not yet implemented');
}

// Constants that define the interface contract
const STUB_VERSION = '0.1.0';

const EXPECTED_INPUT_SCHEMA = {
  field1: 'string',
  field2: 'number',
  // Add expected fields
};

const EXPECTED_OUTPUT_SCHEMA = {
  result: 'string',
  metadata: 'object',
  // Add expected output fields
};

/**
 * Type definitions (for TypeScript conversion)
 *
 * @typedef {Object} StubInputType
 * @property {string} field1
 * @property {number} field2
 *
 * @typedef {Object} StubOutputType
 * @property {string} result
 * @property {Object} metadata
 */

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    StubClass,
    stubFunction,
    stubAsyncFunction,
    NotImplementedError,
    STUB_VERSION,
    EXPECTED_INPUT_SCHEMA,
    EXPECTED_OUTPUT_SCHEMA,
  };
}

// ES6 module export (comment out if using CommonJS)
// export {
//   StubClass,
//   stubFunction,
//   stubAsyncFunction,
//   NotImplementedError,
//   STUB_VERSION,
//   EXPECTED_INPUT_SCHEMA,
//   EXPECTED_OUTPUT_SCHEMA,
// };

// Minimal test when run directly
if (typeof require !== 'undefined' && require.main === module) {
  console.log('[STUB] This module is a stub and not fully implemented');
  console.log(`Version: ${STUB_VERSION}`);
  console.log('TODO: Replace with actual implementation');
}
