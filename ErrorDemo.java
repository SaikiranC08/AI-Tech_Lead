public class ErrorDemo { 
    public static void main(String[] args) {
        System.out.println("This file contains intentional errors for testing");
        
        // Missing semicolon
        String message = "Hello World"
        
        // Unused variable
        int unusedVariable = 42;
        
        // Potential null pointer dereference
        String nullString = null;
        System.out.println(nullString.length());
        
        // Infinite loop
        while(true) {
            break; // Actually not infinite, but looks suspicious
        }
        
        // Missing return statement
        getValue();
    }
    
    // Method without return statement
    public static int getValue() {
        // Missing return statement
    }
    
    // Security issue - hardcoded password
    private static final String PASSWORD = "admin123";
    
    // Performance issue - inefficient string concatenation
    public static String buildString() {
        String result = "";
        for(int i = 0; i < 1000; i++) {
            result += "item" + i;
        }
        return result;
    }
}